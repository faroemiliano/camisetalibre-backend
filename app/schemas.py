import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RegisterInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(max_length=254)
    password: str = Field(min_length=8, max_length=1024)

    @field_validator("name", "email", mode="before")
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str):
        if not re.fullmatch(r"\S+@\S+\.\S+", value):
            raise ValueError("Email inválido")
        return value.lower()


class LoginInput(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=1024)


class Customer(BaseModel):
    id: str
    name: str
    email: str
    createdAt: str


class SessionResponse(BaseModel):
    user: Customer
    token: str


class CustomerResponse(BaseModel):
    user: Customer


class ProjectInput(BaseModel):
    name: str | None = None
    design: Any = None
    productId: str | None = Field(default=None, max_length=32)


class Project(BaseModel):
    id: str
    ownerId: str
    name: str
    design: Any
    createdAt: str
    updatedAt: str
    productId: str | None = None


class ProjectResponse(BaseModel):
    project: Project


class ProjectsResponse(BaseModel):
    projects: list[Project]


class OrderLineInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    productId: str = Field(min_length=1, max_length=32)
    fabricId: str = Field(min_length=1, max_length=32)
    sizeId: str = Field(min_length=1, max_length=16)
    quantity: int = Field(ge=1, le=10000, strict=True)
    projectId: str | None = Field(default=None, max_length=64)


class QuoteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[OrderLineInput] = Field(min_length=1, max_length=100)


class OrderInput(QuoteInput):
    addressId: str | None = Field(default=None, max_length=36)
    notes: str | None = Field(default=None, max_length=1000)


class AddressInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    recipient: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=5, max_length=40)
    street: str = Field(min_length=3, max_length=200)
    apartment: str | None = Field(default=None, max_length=100)
    city: str = Field(min_length=2, max_length=100)
    province: str = Field(min_length=2, max_length=100)
    postalCode: str = Field(min_length=2, max_length=20)
    country: str = Field(default="AR", pattern=r"^[A-Z]{2}$")


class ProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str | None = Field(default=None, min_length=2, max_length=100)
    phone: str | None = Field(default=None, max_length=40)
