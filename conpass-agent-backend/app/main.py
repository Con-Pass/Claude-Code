# flake8: noqa: E402
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import api_router
from app.core.config import settings
from app.core.logging_config import setup_logging, get_logger

# from app.core.observability import init_observability
from app.core.model_settings import init_model_settings
from app.core.middleware import JWTAuthMiddleware

# Initialize logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown."""
    logger.info("Starting ConPass AI Agent Backend...")

    # Initialize services
    init_model_settings()
    # init_observability()

    # Load feature flags and normalization dictionaries from Firestore
    try:
        from app.services.chatbot.feature_flags import load_flags_from_firestore
        await load_flags_from_firestore()
    except Exception as e:
        logger.warning(f"Failed to load feature flags: {e}")

    try:
        from app.services.chatbot.tools.metadata_search.fuzzy_company_matcher import (
            load_normalization_dict,
        )
        await load_normalization_dict()
    except Exception as e:
        logger.warning(f"Failed to load normalization dict: {e}")

    logger.info("Services initialized successfully")

    yield

    logger.info("Shutting down ConPass AI Agent Backend...")


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="ConPass AI Agent API",
        description="A state of the art AI agent for contract management and analysis",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        servers=[
            {"url": "http://localhost:8000", "description": "Development server"},
            {
                "url": "https://agetn-api-test.con-pass.jp",
                "description": "Test environment",
            },
            {
                "url": "https://agent-api-staging.con-pass.jp",
                "description": "Staging environment",
            },
            {
                "url": "https://agent-api.con-pass.jp",
                "description": "Production environment",
            },
        ],
        lifespan=lifespan,
    )

    # Setup CORS
    origins = [
        origin.strip()
        for origin in settings.ALLOWED_ORIGINS.split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(JWTAuthMiddleware)
    # Include API routes
    app.include_router(api_router, prefix="/api")

    return app


# Create the application instance before defining routes
app = create_application()


@app.get("/", tags=["root"])
async def root():
    """API root endpoint."""
    return {
        "message": "ConPass AI Agent API",
        "version": "0.1.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "openapi": "/openapi.json",
        "health": "/health",
    }


@app.get("/health", tags=["health"])
async def health_check():
    """Simple health check endpoint."""
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "version": "0.1.0",
        "service": "conpass-agent-backend",
    }


if __name__ == "__main__":
    app_host = settings.APP_HOST
    app_port = settings.APP_PORT
    environment = settings.ENVIRONMENT

    logger.info(f"Starting server on {app_host}:{app_port}")
    uvicorn.run(
        "main:app",
        host=app_host,
        port=app_port,
        reload=environment == "development",
    )
