"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api.routes import router
from app.core.body_limit import BodyLimitMiddleware

app = FastAPI(
    title="Word Search Solver API",
    description=(
        "Solve word-search puzzles from a letter grid, with optional "
        "local OCR or explicitly configured remote grid extraction from an image."
    ),
    version="1.0.0",
)
app.add_middleware(BodyLimitMiddleware)
app.include_router(router)
