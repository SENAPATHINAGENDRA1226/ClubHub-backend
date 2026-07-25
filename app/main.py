import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.routers import (
    achievements,
    admin_import,
    alumni,
    auth,
    certificates,
    committees,
    contact,
    dashboard,
    events,
    grievances,
    media,
    onboarding,
    opportunities,
    registrations,
    resources,
    settings as settings_router,
    users,
    verification,
)
from app.ws import router as ws_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

# CORS Middleware setup
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount media static files directory
media_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "media")
os.makedirs(os.path.join(media_dir, "qr"), exist_ok=True)
os.makedirs(os.path.join(media_dir, "certificates"), exist_ok=True)
os.makedirs(os.path.join(media_dir, "uploads"), exist_ok=True)
app.mount("/media", StaticFiles(directory=media_dir), name="media")

# Include API Routers
app.include_router(auth.router)
app.include_router(onboarding.router)
app.include_router(events.router)
app.include_router(registrations.router)
app.include_router(certificates.router)
app.include_router(committees.router)
app.include_router(committees.member_router)
app.include_router(alumni.router)
app.include_router(achievements.router)
app.include_router(resources.router)
app.include_router(opportunities.router)
app.include_router(media.router)
app.include_router(grievances.router)
app.include_router(contact.router)
app.include_router(dashboard.router)
app.include_router(users.router)
app.include_router(admin_import.router)
app.include_router(verification.router)
app.include_router(settings_router.router)

# Include WebSocket Router
app.include_router(ws_router.router)


@app.get("/api/health", tags=["Health"])
async def health_check():
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
    }
