from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.dependencies import CustomerDependency, SessionDependency
from app.models import Customer
from app.schemas import CustomerResponse, LoginInput, RegisterInput, SessionResponse
from app.security import create_token, hash_password, password_matches
from app.serializers import customer_data

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])


@router.post("/register", status_code=201, response_model=SessionResponse)
def register(body: RegisterInput, request: Request, session: SessionDependency):
    user = Customer(name=body.name, email=body.email, password_hash=hash_password(body.password))
    session.add(user)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        if getattr(getattr(error.orig, 'diag', None), 'constraint_name', None) == 'uq_customers_email':
            raise HTTPException(409, "Ya existe una cuenta con ese email.") from error
        raise
    return {"user": customer_data(user), "token": create_token(user.id, request.app.state.settings.secret)}


@router.post("/login", response_model=SessionResponse)
def login(body: LoginInput, request: Request, session: SessionDependency):
    user = session.scalar(select(Customer).where(Customer.email == body.email.strip().lower()))
    if not user or not password_matches(body.password, user.password_hash):
        raise HTTPException(401, "Email o contraseña incorrectos.")
    return {"user": customer_data(user), "token": create_token(user.id, request.app.state.settings.secret)}


@router.get("/me", response_model=CustomerResponse)
def me(user: CustomerDependency):
    return {"user": customer_data(user)}
