from fastapi import APIRouter
from sqlalchemy import select

from app.dependencies import CustomerDependency, SessionDependency
from app.models import Address
from app.schemas import AddressInput, ProfileInput
from app.serializers import address_data, customer_data

router = APIRouter(prefix="/api/customers/me", tags=["Clientes"])


@router.get("")
def profile(user: CustomerDependency):
    return {"user": {**customer_data(user), "phone": user.phone}}


@router.patch("")
def update_profile(body: ProfileInput, user: CustomerDependency, session: SessionDependency):
    if body.name is not None:
        user.name = body.name
    if "phone" in body.model_fields_set:
        user.phone = body.phone
    session.commit()
    return {"user": {**customer_data(user), "phone": user.phone}}


@router.get("/addresses")
def addresses(user: CustomerDependency, session: SessionDependency):
    rows = session.scalars(select(Address).where(Address.customer_id == user.id).order_by(Address.created_at))
    return {"addresses": [address_data(row) for row in rows]}


@router.post("/addresses", status_code=201)
def create_address(body: AddressInput, user: CustomerDependency, session: SessionDependency):
    fields = body.model_dump(exclude={"postalCode"})
    address = Address(customer_id=user.id, postal_code=body.postalCode, **fields)
    session.add(address)
    session.commit()
    return {"address": address_data(address)}
