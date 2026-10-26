"""Inicialización del catálogo y migración idempotente del JSON anterior."""
import argparse
import json
import shutil
from datetime import datetime, timezone

from sqlalchemy import select

from app.config import Settings
from app.database import Database
from app.models import Customer, Project
from app.seed import seed_catalog


def import_legacy(session, path):
    if not path.exists():
        return {"customers": 0, "projects": 0}
    data = json.loads(path.read_text(encoding="utf-8"))
    counts = {"customers": 0, "projects": 0}
    for item in data.get("users", []):
        existing = session.get(Customer, item["id"])
        email = item["email"].strip().lower()
        if existing:
            if existing.email != email or existing.password_hash != item["passwordHash"]:
                raise ValueError("El cliente existente difiere del JSON. No se sobrescriben datos.")
            continue
        duplicate = session.scalar(select(Customer).where(Customer.email == email))
        if duplicate:
            raise ValueError("Hay un email ya registrado con otro identificador. No se sobrescriben cuentas.")
        session.add(Customer(id=item["id"], name=item["name"], email=email, password_hash=item["passwordHash"],
                             created_at=datetime.fromisoformat(item["createdAt"].replace("Z", "+00:00"))))
        counts["customers"] += 1
    session.flush()
    for item in data.get("projects", []):
        if session.get(Project, item["id"]):
            continue
        if not session.get(Customer, item["ownerId"]):
            raise ValueError("Hay diseños sin cliente asociado. Se cancela la importación.")
        session.add(Project(id=item["id"], owner_id=item["ownerId"], name=item["name"], design=item.get("design", {}),
                            created_at=datetime.fromisoformat(item["createdAt"].replace("Z", "+00:00")),
                            updated_at=datetime.fromisoformat(item["updatedAt"].replace("Z", "+00:00"))))
        counts["projects"] += 1
    session.flush()
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["seed", "import-json"])
    args = parser.parse_args()
    settings = Settings.from_env()
    database = Database(settings.database_url)
    try:
        if args.command == "import-json" and settings.data_file.exists():
            backup = settings.data_file.with_name("store.json.backup-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
            shutil.copy2(settings.data_file, backup)
        with database.sessions.begin() as session:
            if args.command == "seed":
                seed_catalog(session)
                print("Catálogo inicial cargado; los valores existentes se conservaron.")
            else:
                counts = import_legacy(session, settings.data_file)
                print("Importación completada:", counts)
    finally:
        database.close()


if __name__ == "__main__":
    main()
