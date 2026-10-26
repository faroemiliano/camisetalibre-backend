import argparse

import uvicorn

from app.config import Settings


def main():
    parser = argparse.ArgumentParser(description="API de CamisetaLibre con FastAPI")
    parser.add_argument("--reload", action="store_true", help="Recargar al modificar archivos Python")
    args = parser.parse_args()
    settings = Settings.from_env()
    uvicorn.run("app.main:app", host="127.0.0.1", port=settings.port, reload=args.reload, workers=1)


if __name__ == "__main__":
    main()
