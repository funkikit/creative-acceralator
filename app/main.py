import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from app.api import routes_image, routes_summary, routes_validation, routes_variation


load_dotenv(override=False)

app = FastAPI(title="Creative Gen & Validation PoC")

origins_env = os.getenv("CORS_ORIGINS")
if origins_env:
    allowed_origins = [origin.strip() for origin in origins_env.split(",") if origin.strip()]
else:
    allowed_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:4000",
        "http://127.0.0.1:4000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(routes_variation.router)
app.include_router(routes_image.router)
app.include_router(routes_validation.router)
app.include_router(routes_summary.router)

static_dir = Path(os.getenv("STATIC_DIR", "tmp")).resolve()
static_dir.mkdir(parents=True, exist_ok=True)

# ensure key assets (icon, favicon) are available even when STATIC_DIR is relocated
default_static_source = Path("app/static").resolve()
if default_static_source.exists() and default_static_source != static_dir:
    for asset_name in ("icon.png", "favicon.ico"):
        source = default_static_source / asset_name
        target = static_dir / asset_name
        if source.exists() and not target.exists():
            try:
                target.write_bytes(source.read_bytes())
            except OSError:
                pass

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
