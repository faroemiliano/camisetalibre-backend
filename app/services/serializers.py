from datetime import datetime, timezone


def timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def customer_data(user):
    return {"id": user.id, "name": user.name, "email": user.email, "createdAt": timestamp(user.created_at)}


def project_data(project):
    return {"id": project.id, "ownerId": project.owner_id, "name": project.name,
            "productId": project.product_id, "design": project.design,
            "createdAt": timestamp(project.created_at), "updatedAt": timestamp(project.updated_at)}


def address_data(address):
    return {"id": address.id, "recipient": address.recipient, "phone": address.phone,
            "street": address.street, "apartment": address.apartment, "city": address.city,
            "province": address.province, "postalCode": address.postal_code, "country": address.country}


def order_data(order):
    return {"id": order.id, "status": order.status, "currency": order.currency,
            "total": str(order.total), "shippingAddress": order.shipping_address, "notes": order.notes,
            "createdAt": timestamp(order.created_at), "updatedAt": timestamp(order.updated_at),
            "items": [{"id": item.id, "productId": item.product_id, "productName": item.product_name,
                       "fabricId": item.fabric_id, "fabricName": item.fabric_name,
                       "sizeId": item.size_id, "sizeLabel": item.size_label,
                       "projectId": item.project_id, "design": item.design_snapshot,
                       "quantity": item.quantity, "unitPrice": str(item.unit_price),
                       "total": str(item.line_total)} for item in order.items]}
