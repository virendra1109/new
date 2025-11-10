"""FastAPI Application Entry Point"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api.routes import query_router, registry_router
from services.agent_service import agent_service
from utils.loggers import logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup agent on startup/shutdown"""
    logger.info("Initializing Multi-MCP Agent...")
    await agent_service.initialize()
    logger.info("Agent initialized successfully")
    yield
    logger.info("Shutting down agent...")
    await agent_service.shutdown()
    logger.info("Agent shut down successfully")

app = FastAPI(title="Multi-MCP Agent API",description="Orchestrator-based multi-MCP agent system",version="1.0.0",lifespan=lifespan)

app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"],)

# Include routers
app.include_router(query_router, prefix="/api", tags=["Query"])
app.include_router(registry_router, prefix="/api/registry", tags=["MCP Registry"])