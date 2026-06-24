from fastapi import APIRouter

from yontai.api.routes import (
    benchmarks,
    datasets,
    deployments,
    diagnostics,
    exports,
    files,
    jobs,
    knowledge,
    models,
    projects,
    rag_routes,
    system,
    training,
)

api_router = APIRouter()
api_router.include_router(system.router, prefix="/system", tags=["system"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(datasets.router, prefix="/datasets", tags=["datasets"])
api_router.include_router(training.router, prefix="/training", tags=["training"])
api_router.include_router(benchmarks.router, prefix="/benchmarks", tags=["benchmarks"])
api_router.include_router(diagnostics.router, prefix="/diagnostics", tags=["diagnostics"])
api_router.include_router(exports.router, prefix="/exports", tags=["exports"])
api_router.include_router(deployments.router, prefix="/deployments", tags=["deployments"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(files.router, prefix="/files", tags=["files"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
api_router.include_router(rag_routes.router, prefix="/rag", tags=["rag"])
