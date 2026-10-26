from collections import Counter
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException

from app.models import FabricTier, Product, Size


def calculate_items(items, session):
    quantities = Counter()
    products = {}
    result = []
    for item in items:
        product = session.get(Product, item.productId)
        fabric = session.get(FabricTier, item.fabricId)
        size = session.get(Size, item.sizeId)
        if not product or not product.active or not fabric or not fabric.active or not size:
            raise HTTPException(422, "Producto, tela o talle no disponible.")
        quantities[product.id] += item.quantity
        products[product.id] = product
        price = (product.base_price * (1 + fabric.increase_percent / Decimal(100))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        result.append({"productId": product.id, "productName": product.name, "fabricId": fabric.id,
                       "fabricName": fabric.name, "sizeId": size.id, "sizeLabel": size.label,
                       "projectId": item.projectId, "quantity": item.quantity,
                       "unitPrice": price, "total": price * item.quantity})
    for product_id, quantity in quantities.items():
        product = products[product_id]
        if quantity < product.minimum_quantity:
            raise HTTPException(422, f"{product.name}: el mínimo es de {product.minimum_quantity} prendas del mismo producto.")
    return result
