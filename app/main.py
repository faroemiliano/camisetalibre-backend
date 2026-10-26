from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.config import Settings
from app.routes import auth, projects, catalog, customers, orders, workspace
from app.database import Database


def create_app(settings: Settings | None = None, database: Database | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    database = database or Database(settings.database_url)

    @asynccontextmanager
    async def lifespan(app):
        with database.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        yield
        database.close()

    app = FastAPI(title="CamisetaLibre API", version="2.0.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.database = database
    app.add_middleware(
        CORSMiddleware, allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        message = "Ruta no encontrada." if error.detail == "Not Found" else str(error.detail)
        return JSONResponse({"error": message}, status_code=error.status_code, headers=error.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        if any(item["type"] == "json_invalid" for item in error.errors()):
            return JSONResponse({"error": "JSON inválido."}, status_code=400)
        message = "Los datos enviados no son válidos. Revisá los campos e intentá nuevamente."
        if request.url.path == "/api/auth/register":
            message = "Ingresá nombre, email válido y una contraseña de al menos 8 caracteres."
        return JSONResponse({"error": message}, status_code=422)

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, error: SQLAlchemyError):
        return JSONResponse({"error": "No pudimos acceder a los datos. Volvé a intentar."}, status_code=503)

    @app.get("/api/health", tags=["Estado"])
    def health():
        with database.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok", "database": "postgresql"}

    app.include_router(auth.router)
    app.include_router(projects.router)
    app.include_router(catalog.router)
    app.include_router(customers.router)
    app.include_router(orders.router)
    app.include_router(workspace.router)
    return app


app = create_app()
