from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.dependencies import CustomerDependency, SessionDependency
from app.schemas.editor import PreferencesInput, WorkspaceInput
from app.db.models import Customer, CustomerPreferences, EditorWorkspace, FabricTier, Product, Project, now
from app.services.serializers import timestamp

router = APIRouter(prefix="/api/customers/me", tags=["Borradores y preferencias"])


def workspace_data(workspace, project):
    return {"document": project.design, "ui": workspace.ui_state, "projectId": project.id,
            "revision": workspace.revision, "updatedAt": timestamp(workspace.updated_at)}


def preferences_data(preferences):
    return {"budget": {"productId": preferences.budget_product_id, "fabricId": preferences.budget_fabric_id,
                       "quantity": preferences.budget_quantity},
            "revision": preferences.revision, "updatedAt": timestamp(preferences.updated_at)}


@router.get("/workspace")
def get_workspace(user: CustomerDependency, session: SessionDependency):
    workspace = session.get(EditorWorkspace, user.id)
    if not workspace:
        return {"workspace": None}
    project = session.scalar(select(Project).where(Project.id == workspace.project_id, Project.owner_id == user.id))
    if not project:
        raise HTTPException(404, "Diseño no encontrado.")
    return {"workspace": workspace_data(workspace, project)}


@router.put("/workspace")
def put_workspace(body: WorkspaceInput, user: CustomerDependency, session: SessionDependency):
    # Lock the owner even on the first save, so concurrent inserts cannot race.
    session.execute(select(Customer.id).where(Customer.id == user.id).with_for_update())
    workspace = session.get(EditorWorkspace, user.id)
    revision = workspace.revision if workspace else 0
    if body.expectedRevision != revision:
        raise HTTPException(409, "Tu diseño cambió en otra pestaña. Recargá el guardado de tu cuenta antes de continuar.")
    if workspace:
        project = session.scalar(select(Project).where(Project.id == workspace.project_id, Project.owner_id == user.id).with_for_update())
        if not project:
            raise HTTPException(404, "Diseño no encontrado.")
    else:
        project = Project(owner_id=user.id, name="Mi conjunto", design={})
        session.add(project)
        session.flush()
        workspace = EditorWorkspace(customer_id=user.id, project_id=project.id, ui_state={})
        session.add(workspace)
    project.design = body.document.model_dump(mode="json", exclude_unset=True)
    # A workspace contains both shirt and shorts; its document records the model.
    project.product_id = None
    project.updated_at = now()
    workspace.ui_state = body.ui.model_dump()
    workspace.revision = revision + 1
    workspace.updated_at = now()
    session.commit()
    return {"workspace": workspace_data(workspace, project)}


@router.get("/preferences")
def get_preferences(user: CustomerDependency, session: SessionDependency):
    preferences = session.get(CustomerPreferences, user.id)
    return {"preferences": preferences_data(preferences) if preferences else None}


@router.put("/preferences")
def put_preferences(body: PreferencesInput, user: CustomerDependency, session: SessionDependency):
    product = session.get(Product, body.budget.productId)
    fabric = session.get(FabricTier, body.budget.fabricId)
    if not product or not product.active or not fabric or not fabric.active:
        raise HTTPException(422, "Producto o tela no disponible.")
    if body.budget.quantity < product.minimum_quantity:
        raise HTTPException(422, f"El mínimo es de {product.minimum_quantity} prendas del mismo producto.")
    session.execute(select(Customer.id).where(Customer.id == user.id).with_for_update())
    preferences = session.get(CustomerPreferences, user.id)
    revision = preferences.revision if preferences else 0
    if body.expectedRevision != revision:
        raise HTTPException(409, "El presupuesto cambió en otra pestaña. Recargá los datos de tu cuenta.")
    if not preferences:
        preferences = CustomerPreferences(customer_id=user.id)
        session.add(preferences)
    preferences.budget_product_id = product.id
    preferences.budget_fabric_id = fabric.id
    preferences.budget_quantity = body.budget.quantity
    preferences.revision = revision + 1
    preferences.updated_at = now()
    session.commit()
    return {"preferences": preferences_data(preferences)}
