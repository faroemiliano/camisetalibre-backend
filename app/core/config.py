import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    secret: str = field(repr=False)
    database_url: str = field(default="postgresql+psycopg://localhost/camisetalibre", repr=False)
    data_file: Path = ROOT / "data" / "store.json"
    port: int = 3001
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")

    @classmethod
    def from_env(cls):
        load_dotenv(ROOT / ".env")
        return cls(
            secret=os.getenv("AUTH_SECRET", "cambiar-esta-clave-en-produccion"),
            database_url=os.getenv("DATABASE_URL", "postgresql+psycopg://localhost/camisetalibre"),
            data_file=Path(os.getenv("DATA_FILE", str(ROOT / "data" / "store.json"))),
            port=int(os.getenv("API_PORT", "3001")),
            cors_origins=tuple(
                origin.strip()
                for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
                if origin.strip()
            ),
        )
