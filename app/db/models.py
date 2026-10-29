"""Modelo relacional PostgreSQL. Importes monetarios exactos, nunca float."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, MetaData, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def new_id():
    return str(uuid4())


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_name)s", "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s", "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    })


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (CheckConstraint("email = lower(email)", name="normalized_email"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    phone: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Address(Base):
    __tablename__ = "customer_addresses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    recipient: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(40))
    street: Mapped[str] = mapped_column(String(200))
    apartment: Mapped[str | None] = mapped_column(String(100))
    city: Mapped[str] = mapped_column(String(100))
    province: Mapped[str] = mapped_column(String(100))
    postal_code: Mapped[str] = mapped_column(String(20))
    country: Mapped[str] = mapped_column(String(2), default="AR")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("base_price > 0", name="positive_price"),
        CheckConstraint("minimum_quantity >= 1", name="positive_minimum"),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(500), default="")
    base_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    minimum_quantity: Mapped[int] = mapped_column(Integer, default=8)
    active: Mapped[bool] = mapped_column(default=True)


class FabricTier(Base):
    __tablename__ = "fabric_tiers"
    __table_args__ = (CheckConstraint("increase_percent >= 0 AND increase_percent <= 1000", name="valid_increase"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    label: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(50))
    increase_percent: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    active: Mapped[bool] = mapped_column(default=True)


class Size(Base):
    __tablename__ = "sizes"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    label: Mapped[str] = mapped_column(String(30))
    position: Mapped[int] = mapped_column(Integer)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"), index=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(80))
    design: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class EditorWorkspace(Base):
    __tablename__ = "editor_workspaces"
    __table_args__ = (CheckConstraint("revision > 0", name="positive_revision"),)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"), unique=True)
    ui_state: Mapped[dict] = mapped_column(JSONB, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class CustomerPreferences(Base):
    __tablename__ = "customer_preferences"
    __table_args__ = (
        CheckConstraint("budget_quantity >= 1 AND budget_quantity <= 10000", name="valid_quantity"),
        CheckConstraint("revision > 0", name="positive_revision"),
    )
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), primary_key=True)
    budget_product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    budget_fabric_id: Mapped[str] = mapped_column(ForeignKey("fabric_tiers.id", ondelete="RESTRICT"))
    budget_quantity: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("total > 0", name="positive_total"),
        CheckConstraint("currency = 'ARS'", name="currency_ars"),
        CheckConstraint("status IN ('pending', 'confirmed', 'production', 'shipped', 'delivered', 'cancelled')", name="valid_status"),
        Index("ix_orders_customer_created", "customer_id", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    currency: Mapped[str] = mapped_column(String(3), default="ARS")
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    shipping_address: Mapped[dict | None] = mapped_column(JSONB)
    notes: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    items: Mapped[list["OrderItem"]] = relationship(cascade="all, delete-orphan", order_by="OrderItem.position")


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="positive_quantity"),
        CheckConstraint("unit_price > 0 AND line_total = quantity * unit_price", name="valid_amount"),
        UniqueConstraint("order_id", "position"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    fabric_id: Mapped[str] = mapped_column(ForeignKey("fabric_tiers.id", ondelete="RESTRICT"))
    size_id: Mapped[str] = mapped_column(ForeignKey("sizes.id", ondelete="RESTRICT"))
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    position: Mapped[int] = mapped_column(Integer)
    product_name: Mapped[str] = mapped_column(String(100))
    fabric_name: Mapped[str] = mapped_column(String(50))
    size_label: Mapped[str] = mapped_column(String(30))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    design_snapshot: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSONB)


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="positive_amount"),
        CheckConstraint("currency = 'ARS'", name="currency_ars"),
        CheckConstraint("status IN ('pending', 'approved', 'rejected', 'refunded')", name="valid_status"),
        UniqueConstraint("provider", "provider_reference"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"), index=True)
    provider: Mapped[str] = mapped_column(String(40))
    provider_reference: Mapped[str | None] = mapped_column(String(200))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="ARS")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
