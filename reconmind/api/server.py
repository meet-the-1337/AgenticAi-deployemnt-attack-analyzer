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

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("reconmind.api.server:app", host="127.0.0.1", port=8000, reload=True)
