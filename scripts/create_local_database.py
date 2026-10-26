"""Crear únicamente la base local y el rol propios de CamisetaLibre."""
import getpass
import os
import secrets
from pathlib import Path

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parent.parent
DATABASE = "camisetalibre"
ROLE = "camisetalibre_app"


def main():
    env = ROOT / ".env"
    if env.exists():
        raise SystemExit("Ya existe .env. Se conserva su configuración; no se modifica la base.")
    password = secrets.token_urlsafe(32)
    admin = os.getenv("POSTGRES_ADMIN_URL", f"host=127.0.0.1 port=5432 dbname=postgres user={getpass.getuser()}")
    with psycopg.connect(admin, autocommit=True) as connection:
        exists = connection.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DATABASE,)).fetchone()
        role = connection.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (ROLE,)).fetchone()
        if exists or role:
            raise SystemExit("La base o el rol ya existen. Se conservan sin modificar.")
        connection.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE").format(sql.Identifier(ROLE), sql.Literal(password)))
        try:
            connection.execute(sql.SQL("CREATE DATABASE {} OWNER {} ENCODING 'UTF8'").format(sql.Identifier(DATABASE), sql.Identifier(ROLE)))
        except Exception:
            connection.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(ROLE)))
            raise
    url = f"postgresql+psycopg://{ROLE}:{password}@127.0.0.1:5432/{DATABASE}"
    # Conservar el secreto previo mantiene válidas las sesiones de clientes.
    secret = os.getenv("AUTH_SECRET", "cambiar-esta-clave-en-produccion")
    content = f"API_PORT=3001\nAUTH_SECRET={secret}\nDATABASE_URL={url}\nCORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173\n"
    fd = os.open(env, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as output:
        output.write(content)
    print("Base camisetalibre y rol camisetalibre_app creados. Credenciales guardadas en .env (privado).")


if __name__ == "__main__":
    main()
