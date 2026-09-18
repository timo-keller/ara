"""FastAPI application entry point."""

import uvicorn
from fastapi import FastAPI


def create_app() -> FastAPI:
    """Create the ARA API application."""
    app = FastAPI(title="ARA")

    @app.get("/")
    async def index() -> dict[str, str]:
        return {"message": "ARA API"}

    return app


app = create_app()


def run() -> None:
    """Run the development server."""
    uvicorn.run("ara.main:app", host="127.0.0.1", port=8000)
