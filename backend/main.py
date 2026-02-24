"""
FastAPI backend for lead scoring engine.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes.diagnostic import router as diagnostic_router

app = FastAPI(
    title="Lead Scoring Engine API",
    description="Diagnostic endpoint for business lead enrichment",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(diagnostic_router)


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}


# Mount POST /diagnostic at root path as well for convenience
# The router has prefix="/diagnostic", so POST /diagnostic/diagnostic would be wrong.
# Actually the router prefix is /diagnostic, and the route is "" so the full path is POST /diagnostic. Good.
