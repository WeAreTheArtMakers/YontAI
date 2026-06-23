from sqlalchemy import select
from sqlalchemy.orm import Session

from yontai.db.models import Project, Workspace


class ProjectRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self) -> list[Project]:
        return list(self.db.scalars(select(Project).order_by(Project.created_at.desc())))

    def get(self, project_id: str) -> Project | None:
        return self.db.get(Project, project_id)

    def add(self, project: Project) -> Project:
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project


class WorkspaceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self) -> list[Workspace]:
        return list(self.db.scalars(select(Workspace).order_by(Workspace.created_at.desc())))

    def add(self, workspace: Workspace) -> Workspace:
        self.db.add(workspace)
        self.db.commit()
        self.db.refresh(workspace)
        return workspace
