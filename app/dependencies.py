from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.security import read_token
from app.models import Customer

bearer = HTTPBearer(auto_error=False)


def get_session(request: Request):
    with request.app.state.database.sessions() as session:
        yield session


SessionDependency = Annotated[Session, Depends(get_session)]


def require_customer(
    request: Request,
    session: SessionDependency,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Customer:
    user_id = read_token(credentials.credentials, request.app.state.settings.secret) if credentials else None
    if not user_id:
        raise HTTPException(401, "Iniciá sesión para continuar.", headers={"WWW-Authenticate": "Bearer"})
    user = session.get(Customer, user_id)
    if not user:
        raise HTTPException(401, "Sesión no válida.", headers={"WWW-Authenticate": "Bearer"})
    return user


CustomerDependency = Annotated[Customer, Depends(require_customer)]
