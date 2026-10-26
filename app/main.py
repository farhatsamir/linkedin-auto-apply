from fastapi import FastAPI  # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # type: ignore
from app.database.database import Base, engine  # type: ignore
from app.routers import user_router, auth_router  # type: ignore
from app.routers.settings_router import router as settings_router  # type: ignore
from app.routers.linkedin_session_router import router as linkedin_session_router  # type: ignore
from app.routers.applications_router import router as applications_router  # type: ignore
from app.routers.logs_router import router as logs_router  # type: ignore
from app.routers.auto_apply_router import router as auto_apply_router  # type: ignore
from app.routers.cv_router import router as cv_router
from app.routers.job_router import router as job_router
from app.routers.session_file_router import router as session_file_router
from app.models.auto_apply_run import AutoApplyRun  # noqa: F401 — registers model with Base
from app.core.config import settings

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="LinkedIn Auto Apply API",
    version="1.0.0",
    description="Production API for automated LinkedIn job applications",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(user_router.router)
app.include_router(auth_router.router)
app.include_router(settings_router)
app.include_router(linkedin_session_router)
app.include_router(applications_router)
app.include_router(logs_router)
app.include_router(auto_apply_router)
app.include_router(cv_router)
app.include_router(job_router)
app.include_router(session_file_router)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
def health_check():
    import os
    from sqlalchemy import text # type: ignore

    db_ok = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    return {
        "status": "ok" if db_ok else "degraded",
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "database": "connected" if db_ok else "unreachable",
    }


@app.get("/")
def home():
    return {"message": "LinkedIn Auto Apply API is running!"}