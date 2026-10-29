from fastapi import APIRouter
from sqlalchemy import select

from app.dependencies import SessionDependency
from app.db.models import FabricTier, Product, Size
from app.services.pricing import calculate_items
from app.schemas.api import QuoteInput

router = APIRouter(tags=["Catálogo y presupuestos"])


@router.get("/api/catalog")
def catalog(session: SessionDependency):
    products = session.scalars(select(Product).where(Product.active).order_by(Product.base_price.desc()))
    fabrics = session.scalars(select(FabricTier).where(FabricTier.active).order_by(FabricTier.increase_percent))
    sizes = session.scalars(select(Size).order_by(Size.position))
    return {
        "currency": "ARS",
        "products": [{"id": product.id, "name": product.name, "description": product.description,
                      "basePrice": str(product.base_price), "minimumQuantity": product.minimum_quantity} for product in products],
        "fabrics": [{"id": fabric.id, "label": fabric.label, "name": fabric.name,
                     "increasePercent": str(fabric.increase_percent)} for fabric in fabrics],
        "sizes": [{"id": size.id, "label": size.label} for size in sizes],
    }


@router.post("/api/quotes")
def quote(body: QuoteInput, session: SessionDependency):
    items = calculate_items(body.items, session)
    return {"currency": "ARS", "items": [{**item, "unitPrice": str(item["unitPrice"]), "total": str(item["total"])} for item in items],
            "total": str(sum(item["total"] for item in items))}
