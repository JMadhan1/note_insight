from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth import get_current_uid
from .config import get_settings
from .routers import health, notes


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Note Insight API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(notes.router)

    @app.get("/me")
    def me(uid: str = Depends(get_current_uid)) -> dict:
        """Minimal authenticated echo route — proves token verification works
        end to end independent of Firestore/Gemini."""
        return {"uid": uid}

    return app


app = create_app()
