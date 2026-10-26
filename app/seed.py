"""Catálogo inicial. No sobrescribe precios ni productos ya configurados."""
from decimal import Decimal

from sqlalchemy.dialects.postgresql import insert

from app.models import FabricTier, Product, Size

PRODUCTS = [
    {"id": "camiseta", "name": "Camiseta", "base_price": Decimal("28000.00")},
    {"id": "chomba", "name": "Chomba", "base_price": Decimal("31000.00")},
    {"id": "musculosa", "name": "Musculosa", "base_price": Decimal("20000.00")},
    {"id": "short", "name": "Short", "base_price": Decimal("18000.00")},
]
FABRICS = [
    {"id": "eco", "label": "Precio 1", "name": "Eco", "increase_percent": Decimal("0")},
    {"id": "pro", "label": "Precio 2", "name": "Pro", "increase_percent": Decimal("20")},
    {"id": "premium", "label": "Precio 3", "name": "Premium", "increase_percent": Decimal("30")},
]


def seed_catalog(session):
    for model, rows in ((Product, PRODUCTS), (FabricTier, FABRICS), (Size, [
        {"id": size, "label": size, "position": index}
        for index, size in enumerate(("XS", "S", "M", "L", "XL", "XXL", "3XL"))
    ])):
        session.execute(insert(model).values(rows).on_conflict_do_nothing(index_elements=["id"]))
