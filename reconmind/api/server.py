import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from reconmind.api.routes import router

logger = logging.getLogger(__name__)

app = FastAPI(title="ReconMind API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import os
from fastapi.staticfiles import StaticFiles

app.include_router(router)

# Serve production frontend if available
dist_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.exists(dist_dir):
    logger.info(f"Serving static frontend from {dist_dir}")
    app.mount("/", StaticFiles(directory=dist_dir, html=True), name="frontend")
else:
    logger.warning("frontend/dist not found, static UI will not be served.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("reconmind.api.server:app", host="127.0.0.1", port=8000, reload=True)
