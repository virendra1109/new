"""Unified FastAPI Application - Clean approach switcher"""
import sys
import os
from contextlib import asynccontextmanager
from typing import Literal, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import mlflow
import uuid

# Setup paths
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
APPROACH1_PATH = os.path.join(PROJECT_ROOT, "approach1")
APPROACH2_PATH = os.path.join(PROJECT_ROOT, "approach2")

# Add both to path
sys.path.insert(0, APPROACH1_PATH)
sys.path.insert(0, APPROACH2_PATH)

# Import handlers
approach1_service = None
approach2_handlers = None

try:
    from approach1.services.agent_service import agent_service as approach1_service
    from approach1.api.models import QueryRequest as A1QueryRequest, QueryResponse as A1QueryResponse
    APPROACH1_AVAILABLE = True
    print("✓ Approach1 loaded")
except Exception as e:
    print(f"✗ Approach1 failed: {e}")
    APPROACH1_AVAILABLE = False
    A1QueryRequest = A1QueryResponse = None

try:
    from approach2.api.database import AgentDatabase
    from approach2.api.routes import APIHandlers
    from approach2.api.mcp_loaders import load_mcp_servers_from_config
    from approach2.api.agent_loaders import load_code_based_agents, merge_agents
    from approach2.api.models import QueryRequest as A2QueryRequest, QueryResponse as A2QueryResponse
    
    # Initialize approach2
    DATABASE_URL = "postgresql://neondb_owner:npg_4gRWNunLYJ1d@ep-icy-voice-a8cstquo-pooler.eastus2.azure.neon.tech/neondb?sslmode=require&channel_binding=require"
    db = AgentDatabase(DATABASE_URL)
    approach2_handlers = APIHandlers(db)
    approach2_handlers.mcp_servers = load_mcp_servers_from_config()
    code_agents = load_code_based_agents()
    db_agents = db.load_all_agents()
    approach2_handlers.agents_cache = merge_agents(code_agents, db_agents)
    
    APPROACH2_AVAILABLE = True
    print("✓ Approach2 loaded")
except Exception as e:
    print(f"✗ Approach2 failed: {e}")
    APPROACH2_AVAILABLE = False
    A2QueryRequest = A2QueryResponse = None

# MLflow setup
mlflow.set_tracking_uri("file:///D:/mlflow_tracking")
mlflow.openai.autolog()

# Models
class QueryInput(BaseModel):
    query: str = Field(..., description="Query to process")
    session_id: Optional[str] = Field(None, description="Session ID")
    approach: Literal["approach1", "approach2"] = Field("approach1", description="Approach")

class ClearSessionInput(BaseModel):
    session_id: str = Field(..., description="Session ID")
    approach: Literal["approach1", "approach2"] = Field("approach1", description="Approach")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize approaches on startup"""
    if APPROACH1_AVAILABLE and approach1_service:
        await approach1_service.initialize()
        print("✓ Approach1 initialized")
    
    yield
    
    if APPROACH1_AVAILABLE and approach1_service:
        await approach1_service.shutdown()

# Create app
app = FastAPI(
    title="Unified Multi-Agent API",
    description="Switch between Approach1 (direct MCP) and Approach2 (Magentic)",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/query")
async def process_query(request: QueryInput):
    """Process query using specified approach"""
    exp_id = mlflow.create_experiment(f"unified-{uuid.uuid4()}")
    
    with mlflow.start_run(run_name=f"{request.approach}-run", experiment_id=exp_id):
        if request.approach == "approach1":
            if not APPROACH1_AVAILABLE:
                raise HTTPException(400, "Approach1 not available")
            
            result = await approach1_service.process_query(
                query=request.query,
                session_id=request.session_id
            )
            
            return A1QueryResponse(
                success=True,
                query=request.query,
                plan=result["plan"],
                selected_tools=result["selected_tools"],
                result=result["result"],
                session_id=result.get("session_id")
            )
        
        elif request.approach == "approach2":
            if not APPROACH2_AVAILABLE:
                raise HTTPException(400, "Approach2 not available")
            
            a2_request = A2QueryRequest(
                query=request.query,
                session_id=request.session_id
            )
            
            return await approach2_handlers.execute_query(a2_request)
        
        else:
            raise HTTPException(400, f"Invalid approach: {request.approach}")

@app.post("/clear-session")
async def clear_session(request: ClearSessionInput):
    """Clear session for specified approach"""
    if request.approach == "approach1":
        if not APPROACH1_AVAILABLE:
            raise HTTPException(400, "Approach1 not available")
        
        await approach1_service.clear_session(request.session_id)
        return {
            "success": True,
            "message": f"Session '{request.session_id}' cleared",
            "session_id": request.session_id
        }
    
    elif request.approach == "approach2":
        if not APPROACH2_AVAILABLE:
            raise HTTPException(400, "Approach2 not available")
        
        from approach2.api.models import ClearSessionRequest
        a2_request = ClearSessionRequest(session_id=request.session_id)
        return await approach2_handlers.clear_session(a2_request)
    
    else:
        raise HTTPException(400, f"Invalid approach: {request.approach}")

# Additional endpoints for frontend compatibility
@app.post("/sessions")
async def create_session(approach: Literal["approach1", "approach2"] = "approach2"):
    """Create a new session"""
    if approach == "approach1" and APPROACH1_AVAILABLE:
        # Approach1 doesn't have explicit session creation, generate UUID
        import uuid
        return {"session_id": str(uuid.uuid4())}
    elif approach == "approach2" and APPROACH2_AVAILABLE:
        import uuid
        return {"session_id": str(uuid.uuid4())}
    else:
        raise HTTPException(400, f"Approach '{approach}' not available")

@app.get("/agents")
async def list_agents():
    """List all agents (only available in Approach2)"""
    if not APPROACH2_AVAILABLE or not approach2_handlers:
        raise HTTPException(400, "Approach2 not available")
    
    agents = approach2_handlers.agents_cache
    agent_list = list(agents.keys())
    
    return {
        "agents": agent_list,
        "details": agents
    }

@app.post("/agents")
async def add_agent(agent_data: dict):
    """Add new agent (only available in Approach2)"""
    if not APPROACH2_AVAILABLE or not approach2_handlers:
        raise HTTPException(400, "Approach2 not available")
    
    from approach2.api.models import AgentConfig
    try:
        agent_config = AgentConfig(**agent_data)
        approach2_handlers.db.create_agent(agent_data)
        
        # Reload agents cache
        code_agents = load_code_based_agents()
        db_agents = approach2_handlers.db.load_all_agents()
        approach2_handlers.agents_cache = merge_agents(code_agents, db_agents)
        
        return {"message": f"Agent '{agent_data['name']}' created successfully"}
    except Exception as e:
        raise HTTPException(500, f"Failed to create agent: {str(e)}")

@app.delete("/agents/{agent_name}")
async def delete_agent(agent_name: str):
    """Delete agent (only available in Approach2)"""
    if not APPROACH2_AVAILABLE or not approach2_handlers:
        raise HTTPException(400, "Approach2 not available")
    
    try:
        success = approach2_handlers.db.delete_agent(agent_name)
        if not success:
            raise HTTPException(404, "Agent not found")
        
        # Reload agents cache
        code_agents = load_code_based_agents()
        db_agents = approach2_handlers.db.load_all_agents()
        approach2_handlers.agents_cache = merge_agents(code_agents, db_agents)
        
        return {"message": f"Agent '{agent_name}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to delete agent: {str(e)}")

@app.get("/mcp-servers")
async def list_servers():
    """List all MCP servers (only available in Approach2)"""
    if not APPROACH2_AVAILABLE or not approach2_handlers:
        raise HTTPException(400, "Approach2 not available")
    
    servers = approach2_handlers.mcp_servers
    server_list = list(servers.keys())
    
    details = {}
    for name, server in servers.items():
        details[name] = {
            "name": name,
            "type": server.get("type", "command"),
            "description": server.get("description", ""),
            "tools_count": len(server.get("tools", [])),
            "status": "active"
        }
    
    return {
        "servers": server_list,
        "details": details
    }

@app.post("/mcp-servers")
async def add_server(server_data: dict):
    """Add new MCP server (only available in Approach2)"""
    if not APPROACH2_AVAILABLE or not approach2_handlers:
        raise HTTPException(400, "Approach2 not available")
    
    try:
        name = server_data.get("name")
        if name in approach2_handlers.mcp_servers:
            raise HTTPException(400, f"Server '{name}' already exists")
        
        approach2_handlers.mcp_servers[name] = {
            "name": name,
            "type": server_data.get("type", "command"),
            "description": server_data.get("description", ""),
            "command": server_data.get("command"),
            "args": server_data.get("args", []),
            "env": server_data.get("env", {}),
            "endpoint": server_data.get("endpoint"),
            "tools": [],
            "status": "active"
        }
        
        return {
            "success": True,
            "message": f"Server '{name}' added successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to add server: {str(e)}")

@app.delete("/mcp-servers/{server_name}")
async def delete_server(server_name: str):
    """Delete MCP server (only available in Approach2)"""
    if not APPROACH2_AVAILABLE or not approach2_handlers:
        raise HTTPException(400, "Approach2 not available")
    
    if server_name not in approach2_handlers.mcp_servers:
        raise HTTPException(404, f"Server '{server_name}' not found")
    
    del approach2_handlers.mcp_servers[server_name]
    
    return {
        "success": True,
        "message": f"Server '{server_name}' deleted successfully"
    }

@app.get("/")
async def root():
    """API information"""
    return {
        "message": "Unified Multi-Agent API",
        "approaches": {
            "approach1": APPROACH1_AVAILABLE,
            "approach2": APPROACH2_AVAILABLE
        },
        "usage": {
            "query": "POST /query with {'query': '...', 'approach': 'approach1|approach2'}",
            "clear_session": "POST /clear-session with {'session_id': '...', 'approach': 'approach1|approach2'}"
        }
    }

@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "approach1": APPROACH1_AVAILABLE,
        "approach2": APPROACH2_AVAILABLE
    }

if __name__ == "__main__":
    import uvicorn
    print(f"\n{'='*70}")
    print("Unified Multi-Agent API")
    print(f"{'='*70}")
    print(f"Approach1: {'✓ Available' if APPROACH1_AVAILABLE else '✗ Not Available'}")
    print(f"Approach2: {'✓ Available' if APPROACH2_AVAILABLE else '✗ Not Available'}")
    print(f"{'='*70}\n")
    uvicorn.run(app, port=8000)