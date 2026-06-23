from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from yontai.db.models import Project, Workspace
from yontai.db.session import get_db
from yontai.repositories.projects import ProjectRepository, WorkspaceRepository
from yontai.schemas.projects import ProjectCreate, ProjectRead, WorkspaceCreate, WorkspaceRead

router = APIRouter()


@router.get("", response_model=list[ProjectRead])
def list_projects(db: Session = Depends(get_db)) -> list[Project]:
    return ProjectRepository(db).list()


@router.post("", response_model=ProjectRead, status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> Project:
    return ProjectRepository(db).add(Project(name=payload.name, description=payload.description))


@router.get("/-/workspaces", response_model=list[WorkspaceRead])
def list_workspaces(db: Session = Depends(get_db)) -> list[Workspace]:
    return WorkspaceRepository(db).list()


@router.post("/-/workspaces", response_model=WorkspaceRead, status_code=201)
def create_workspace(payload: WorkspaceCreate, db: Session = Depends(get_db)) -> Workspace:
    project = ProjectRepository(db).get(payload.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Proje bulunamadı.")
    workspace = Workspace(**payload.model_dump())
    return WorkspaceRepository(db).add(workspace)


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: str, db: Session = Depends(get_db)) -> Project:
    project = ProjectRepository(db).get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Proje bulunamadı.")
    return project
