from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.dependencies import CustomerDependency, SessionDependency
from app.db.models import Customer, EditorWorkspace, Product, Project, now
from app.schemas.api import ProjectInput, ProjectResponse, ProjectsResponse
from app.services.serializers import project_data

router = APIRouter(prefix="/api/projects", tags=["Diseños"])


def validate_product(product_id, session):
    if product_id is not None:
        product = session.get(Product, product_id)
        if not product or not product.active:
            raise HTTPException(422, "El producto seleccionado no está disponible.")


@router.get("", response_model=ProjectsResponse)
def list_projects(user: CustomerDependency, session: SessionDependency):
    projects = session.scalars(select(Project).where(Project.owner_id == user.id).order_by(Project.created_at.desc()))
    return {"projects": [project_data(project) for project in projects]}


@router.post("", status_code=201, response_model=ProjectResponse)
def create_project(body: ProjectInput, user: CustomerDependency, session: SessionDependency):
    validate_product(body.productId, session)
    project = Project(owner_id=user.id, product_id=body.productId,
                      name=(body.name if body.name is not None else "Diseño sin título")[:80],
                      design=body.design if body.design is not None else {})
    session.add(project)
    session.commit()
    return {"project": project_data(project)}


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(project_id: str, body: ProjectInput, user: CustomerDependency, session: SessionDependency):
    session.execute(select(Customer.id).where(Customer.id == user.id).with_for_update())
    project = session.scalar(select(Project).where(Project.id == project_id, Project.owner_id == user.id).with_for_update())
    if not project:
        raise HTTPException(404, "Diseño no encontrado.")
    if "name" in body.model_fields_set:
        project.name = (body.name if body.name is not None else "Diseño sin título")[:80]
    if "design" in body.model_fields_set:
        project.design = body.design
    if "productId" in body.model_fields_set:
        validate_product(body.productId, session)
        project.product_id = body.productId
    workspace = session.scalar(select(EditorWorkspace).where(EditorWorkspace.customer_id == user.id, EditorWorkspace.project_id == project.id))
    if workspace:
        workspace.revision += 1
        workspace.updated_at = now()
    session.commit()
    return {"project": project_data(project)}
