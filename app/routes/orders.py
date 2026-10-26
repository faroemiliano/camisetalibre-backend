from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.dependencies import CustomerDependency, SessionDependency
from app.models import Address, Order, OrderItem, Project
from app.pricing import calculate_items
from app.schemas import OrderInput
from app.serializers import address_data, order_data

router = APIRouter(prefix="/api/orders", tags=["Compras"])


@router.get("")
def list_orders(user: CustomerDependency, session: SessionDependency, limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0)):
    orders = session.scalars(select(Order).where(Order.customer_id == user.id).options(selectinload(Order.items))
                             .order_by(Order.created_at.desc()).limit(limit).offset(offset))
    return {"orders": [order_data(order) for order in orders]}


@router.post("", status_code=201)
def create_order(body: OrderInput, user: CustomerDependency, session: SessionDependency):
    priced = calculate_items(body.items, session)
    address = None
    if body.addressId:
        address = session.scalar(select(Address).where(Address.id == body.addressId, Address.customer_id == user.id))
        if not address:
            raise HTTPException(404, "Dirección no encontrada.")
    order = Order(customer_id=user.id, total=sum(item["total"] for item in priced),
                  shipping_address=address_data(address) if address else None, notes=body.notes)
    for position, item in enumerate(priced):
        design = None
        if item["projectId"]:
            project = session.scalar(select(Project).where(Project.id == item["projectId"], Project.owner_id == user.id))
            if not project:
                raise HTTPException(404, "Diseño no encontrado.")
            if project.product_id and project.product_id != item["productId"]:
                raise HTTPException(422, "El diseño no corresponde al producto seleccionado.")
            design = project.design
        order.items.append(OrderItem(
            position=position, product_id=item["productId"], fabric_id=item["fabricId"], size_id=item["sizeId"],
            project_id=item["projectId"], product_name=item["productName"], fabric_name=item["fabricName"],
            size_label=item["sizeLabel"], quantity=item["quantity"], unit_price=item["unitPrice"],
            line_total=item["total"], design_snapshot=design,
        ))
    session.add(order)
    session.commit()
    return {"order": order_data(order)}


@router.get("/{order_id}")
def get_order(order_id: str, user: CustomerDependency, session: SessionDependency):
    order = session.scalar(select(Order).where(Order.id == order_id, Order.customer_id == user.id).options(selectinload(Order.items)))
    if not order:
        raise HTTPException(404, "Compra no encontrada.")
    return {"order": order_data(order)}


@router.post("/{order_id}/cancel")
def cancel_order(order_id: str, user: CustomerDependency, session: SessionDependency):
    order = session.scalar(select(Order).where(Order.id == order_id, Order.customer_id == user.id).with_for_update())
    if not order:
        raise HTTPException(404, "Compra no encontrada.")
    if order.status != "pending":
        raise HTTPException(409, "Solo se pueden cancelar compras pendientes.")
    order.status = "cancelled"
    session.commit()
    return {"order": order_data(order)}
