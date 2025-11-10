"""FastAPI application with static file serving and MLflow tracking."""
import sys
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import modules
from api.database import AgentDatabase
from api.routes import APIHandlers
from api.mcp_loaders import load_mcp_servers_from_config
from api.agent_loaders import load_code_based_agents, merge_agents
from api.models import (
    MCPServerConfig, AgentConfig, QueryRequest,
    QueryResponse, AgentListResponse, MCPServerListResponse,
    ClearSessionRequest, ClearSessionResponse
)
from utils.logger_config import magentic_logger
import mlflow
import uuid
mlflow.set_tracking_uri("file:///D:/mlflow_tracking")
mlflow.openai.autolog()

# Database configuration
DATABASE_URL = "postgresql://neondb_owner:npg_4gRWNunLYJ1d@ep-icy-voice-a8cstquo-pooler.eastus2.azure.neon.tech/neondb?sslmode=require&channel_binding=require"

# Initialize database and handlers
db = AgentDatabase(DATABASE_URL)
handlers = APIHandlers(db)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    magentic_logger.info("\n" + "="*70)
    magentic_logger.info("STARTING API - LOADING CONFIGURATION")
    magentic_logger.info("="*70)
    
    # Load MCP servers
    magentic_logger.info("\n1. Loading MCP Servers...")
    try:
        mcp_servers = load_mcp_servers_from_config()
        handlers.mcp_servers = mcp_servers
        magentic_logger.info(f"Loaded {len(mcp_servers)} MCP servers: {list(mcp_servers.keys())}")
    except Exception as e:
        magentic_logger.error(f"Failed to load MCP servers: {e}")
        handlers.mcp_servers = {}
    
    # Load code-based agents
    magentic_logger.info("\n2. Loading Code-Based Agents...")
    try:
        code_agents = load_code_based_agents()
        magentic_logger.info(f"  Loaded {len(code_agents)} code-based agents: {list(code_agents.keys())}")
    except Exception as e:
        magentic_logger.error(f"   Failed to load code-based agents: {e}")
        code_agents = {}
    
    # Load database agents
    magentic_logger.info("\n3. Loading Database Agents...")
    try:
        db_agents = db.load_all_agents()
        magentic_logger.info(f"  Loaded {len(db_agents)} database agents: {list(db_agents.keys())}")
    except Exception as e:
        magentic_logger.error(f"   Failed to load database agents: {e}")
        db_agents = {}
    
    # Merge agents
    magentic_logger.info("\n4. Merging Agent Pools...")
    handlers.agents_cache = merge_agents(code_agents, db_agents)
    magentic_logger.info(f"  Total agents available: {len(handlers.agents_cache)}")
    
    # Summary
    magentic_logger.info("\n" + "="*70)
    magentic_logger.info("STARTUP COMPLETE - READY TO ACCEPT REQUESTS")
    magentic_logger.info("="*70)
    magentic_logger.info(f"MCP Servers: {list(handlers.mcp_servers.keys())}")
    magentic_logger.info(f"Agents: {list(handlers.agents_cache.keys())}")
    magentic_logger.info("="*70 + "\n")
    
    yield
    
    # Shutdown (if needed)
    magentic_logger.info("Shutting down API...")


# Initialize FastAPI
app = FastAPI(
    title="Multi-Agent Orchestration API",
    description="API for managing agents, MCP servers, and executing queries",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# MCP Server endpoints
@app.post("/mcp-servers", tags=["MCP Servers"])
async def add_mcp_server(server: MCPServerConfig):
    """Register a new MCP server."""
    return await handlers.add_mcp_server(server)


@app.get("/mcp-servers", response_model=MCPServerListResponse, tags=["MCP Servers"])
async def list_mcp_servers():
    """List all MCP servers."""
    return await handlers.list_mcp_servers()


@app.delete("/mcp-servers/{name}", tags=["MCP Servers"])
async def delete_mcp_server(name: str):
    """Delete an MCP server."""
    return await handlers.delete_mcp_server(name)


# Agent endpoints
@app.post("/agents", tags=["Agents"])
async def add_agent(agent: AgentConfig):
    """Register a new agent."""
    return await handlers.add_agent(agent)


@app.get("/agents", response_model=AgentListResponse, tags=["Agents"])
async def list_agents():
    """List all registered agents."""
    return await handlers.list_agents()


@app.get("/agents/{name}", tags=["Agents"])
async def get_agent(name: str):
    """Get agent details by name."""
    return await handlers.get_agent(name)


@app.delete("/agents/{name}", tags=["Agents"])
async def delete_agent(name: str):
    """Delete an agent."""
    return await handlers.delete_agent(name)


# Query execution
@app.post("/query", response_model=QueryResponse, tags=["Execution"])
async def execute_query(request: QueryRequest):
    """Execute a query using agent orchestration with optional session context."""
    exp_id = mlflow.create_experiment(f"multi-mcp-experiment-{uuid.uuid4()}")

    with mlflow.start_run(run_name="multi-mcp-agent-run", experiment_id=exp_id):
        return await handlers.execute_query(request)


# Session management
@app.post("/clear-session", response_model=ClearSessionResponse, tags=["Session Management"])
async def clear_session(request: ClearSessionRequest):
    """Clear conversation context for a specific session."""
    return await handlers.clear_session(request)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, port=8000)