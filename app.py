"""Unified FastAPI Application - Simple approach switcher"""
import sys
import os
from contextlib import asynccontextmanager
from typing import Literal, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import mlflow
import uuid

# Add both approaches to path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
APPROACH1_PATH = os.path.join(PROJECT_ROOT, "approach1")
APPROACH2_PATH = os.path.join(PROJECT_ROOT, "approach2")

sys.path.insert(0, APPROACH1_PATH)
sys.path.insert(0, APPROACH2_PATH)

# Import Approach1 - isolate imports
original_cwd = os.getcwd()
original_sys_path = sys.path.copy()

try:
    # Remove approach2 from path temporarily
    if APPROACH2_PATH in sys.path:
        sys.path.remove(APPROACH2_PATH)
    
    os.chdir(APPROACH1_PATH)
    if APPROACH1_PATH not in sys.path:
        sys.path.insert(0, APPROACH1_PATH)
    
    from approach1.services.agent_service import agent_service as approach1_agent_service
    from approach1.api.routes import process_query as approach1_process_query, clear_session as approach1_clear_session
    from approach1.api.models import QueryRequest as Approach1QueryRequest, QueryResponse as Approach1QueryResponse, ClearSessionRequest as Approach1ClearSessionRequest
    
    APPROACH1_AVAILABLE = True
    print("✓ Approach1 loaded")
except Exception as e:
    print(f"✗ Approach1 not available: {e}")
    import traceback
    traceback.print_exc()
    APPROACH1_AVAILABLE = False
    approach1_agent_service = None
    approach1_process_query = None
    approach1_clear_session = None
    Approach1QueryRequest = None
    Approach1QueryResponse = None
    Approach1ClearSessionRequest = None
finally:
    os.chdir(original_cwd)
    sys.path[:] = original_sys_path

# Import Approach2 - isolate imports
try:
    # Remove approach1 from path temporarily
    if APPROACH1_PATH in sys.path:
        sys.path.remove(APPROACH1_PATH)
    
    os.chdir(APPROACH2_PATH)
    if APPROACH2_PATH not in sys.path:
        sys.path.insert(0, APPROACH2_PATH)
    
    from approach2.api.database import AgentDatabase
    from approach2.api.routes import APIHandlers
    from approach2.api.mcp_loaders import load_mcp_servers_from_config
    from approach2.api.agent_loaders import load_code_based_agents, merge_agents
    from approach2.api.models import QueryRequest as Approach2QueryRequest, QueryResponse as Approach2QueryResponse, ClearSessionRequest as Approach2ClearSessionRequest
    
    APPROACH2_AVAILABLE = True
    print("✓ Approach2 loaded")
except Exception as e:
    print(f"✗ Approach2 not available: {e}")
    import traceback
    traceback.print_exc()
    APPROACH2_AVAILABLE = False
    AgentDatabase = None
    APIHandlers = None
    load_mcp_servers_from_config = None
    load_code_based_agents = None
    merge_agents = None
    Approach2QueryRequest = None
    Approach2QueryResponse = None
    Approach2ClearSessionRequest = None
finally:
    os.chdir(original_cwd)
    sys.path[:] = original_sys_path

# Initialize Approach2 handlers
approach2_handlers = None
if APPROACH2_AVAILABLE:
    try:
        DATABASE_URL = "postgresql://neondb_owner:npg_4gRWNunLYJ1d@ep-icy-voice-a8cstquo-pooler.eastus2.azure.neon.tech/neondb?sslmode=require&channel_binding=require"
        db = AgentDatabase(DATABASE_URL)
        approach2_handlers = APIHandlers(db)
        
        # Load MCP servers and agents
        mcp_servers = load_mcp_servers_from_config()
        approach2_handlers.mcp_servers = mcp_servers
        code_agents = load_code_based_agents()
        db_agents = db.load_all_agents()
        approach2_handlers.agents_cache = merge_agents(code_agents, db_agents)
        print("✓ Approach2 initialized")
    except Exception as e:
        print(f"✗ Approach2 initialization failed: {e}")
        approach2_handlers = None

# Set up MLflow
mlflow.set_tracking_uri("file:///D:/mlflow_tracking")
mlflow.openai.autolog()

# Models
class ApproachType(str):
    APPROACH1 = "approach1"
    APPROACH2 = "approach2"

class QueryInput(BaseModel):
    """Query input with approach selection"""
    query: str = Field(..., description="The query to process")
    session_id: Optional[str] = Field(None, description="Session ID for conversation context")
    approach: Literal["approach1", "approach2"] = Field("approach1", description="Approach to use")

class ClearSessionInput(BaseModel):
    """Clear session input with approach selection"""
    session_id: str = Field(..., description="Session ID to clear")
    approach: Literal["approach1", "approach2"] = Field("approach1", description="Approach to use")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize both approaches on startup"""
    # Initialize Approach1
    if APPROACH1_AVAILABLE and approach1_agent_service:
        try:
            await approach1_agent_service.initialize()
            print("✓ Approach1 initialized")
        except Exception as e:
            print(f"✗ Approach1 initialization failed: {e}")
    
    yield
    
    # Shutdown
    if APPROACH1_AVAILABLE and approach1_agent_service:
        try:
            await approach1_agent_service.shutdown()
        except Exception as e:
            print(f"Error shutting down Approach1: {e}")

# Create FastAPI app
app = FastAPI(
    title="Unified Multi-Agent API",
    description="API supporting both Approach1 and Approach2 - select approach in request",
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

# Query endpoint - approach selection in request
@app.post("/query")
async def process_query(request: QueryInput):
    """
    Process a query using the specified approach.
    Set 'approach' field in request to 'approach1' or 'approach2'
    """
    exp_id = mlflow.create_experiment(f"unified-mcp-experiment-{uuid.uuid4()}")
    
    with mlflow.start_run(run_name=f"{request.approach}-run", experiment_id=exp_id):
        if request.approach == "approach1" and APPROACH1_AVAILABLE:
            # Use Approach1
            a1_request = Approach1QueryRequest(query=request.query, session_id=request.session_id)
            return await approach1_process_query(a1_request)
        
        elif request.approach == "approach2" and APPROACH2_AVAILABLE and approach2_handlers:
            # Use Approach2
            a2_request = Approach2QueryRequest(query=request.query, session_id=request.session_id)
            return await approach2_handlers.execute_query(a2_request)
        
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Approach '{request.approach}' is not available"
            )

# Clear session endpoint - approach selection in request
@app.post("/clear-session")
async def clear_session(request: ClearSessionInput):
    """
    Clear a session using the specified approach.
    Set 'approach' field in request to 'approach1' or 'approach2'
    """
    if request.approach == "approach1" and APPROACH1_AVAILABLE:
        a1_request = Approach1ClearSessionRequest(session_id=request.session_id)
        return await approach1_clear_session(a1_request)
    
    elif request.approach == "approach2" and APPROACH2_AVAILABLE and approach2_handlers:
        a2_request = Approach2ClearSessionRequest(session_id=request.session_id)
        return await approach2_handlers.clear_session(a2_request)
    
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Approach '{request.approach}' is not available"
        )

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Unified Multi-Agent API",
        "available_approaches": {
            "approach1": APPROACH1_AVAILABLE,
            "approach2": APPROACH2_AVAILABLE
        },
        "usage": {
            "query": "POST /query with {'query': '...', 'approach': 'approach1' or 'approach2'}",
            "clear_session": "POST /clear-session with {'session_id': '...', 'approach': 'approach1' or 'approach2'}"
        }
    }

if __name__ == "__main__":
    import uvicorn
    print(f"\n{'='*70}")
    print("Unified Multi-Agent API")
    print(f"{'='*70}")
    print(f"Approach1: {'✓ Available' if APPROACH1_AVAILABLE else '✗ Not Available'}")
    print(f"Approach2: {'✓ Available' if APPROACH2_AVAILABLE else '✗ Not Available'}")
    print(f"{'='*70}\n")
    uvicorn.run(app,  port=8000)
