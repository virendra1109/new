"""API Route Handlers with Session Management"""
from fastapi import APIRouter, HTTPException, status
from api.models import (
    QueryRequest, QueryResponse,
    ClearSessionRequest, ClearSessionResponse,
    AddServerRequest, AddServerResponse,
    RemoveServerRequest, RemoveServerResponse,
    ListServersResponse
)
import mlflow
import uuid
from services.agent_service import agent_service
from services.registry_service import registry_service
from utils.loggers import logger

query_router = APIRouter()
registry_router = APIRouter()

# Query Endpoints
mlflow.set_tracking_uri("file:///D:/mlflow_tracking")
mlflow.openai.autolog()

@query_router.post("/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    """Process a query using the orchestrator agent with optional session context"""
    exp_name = f"multi-mcp-experiment-{uuid.uuid4()}"
    exp_id = mlflow.create_experiment(exp_name)
    with mlflow.start_run(run_name="multi-mcp-agent-run", experiment_id=exp_id):
            try:
                logger.info(f"Processing query: {request.query} (session: {request.session_id})")
                result = await agent_service.process_query(request.query, request.session_id)
                print(result.get('session_id'))
                return QueryResponse(
                    success=True,
                    query=request.query,
                    plan=result["plan"],
                    selected_tools=result["selected_tools"],
                    result=result["result"],
                    session_id=result.get("session_id")
                )
            except Exception as e:
                logger.error(f"Query processing failed: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Query processing failed: {str(e)}"
                )

@query_router.post("/clear-session", response_model=ClearSessionResponse)
async def clear_session(request: ClearSessionRequest):
    """Clear conversation context for a specific session"""
    try:
        logger.info(f"Clearing session: {request.session_id}")
        await agent_service.clear_session(request.session_id)
        return ClearSessionResponse(
            success=True,
            message=f"Session '{request.session_id}' cleared successfully",
            session_id=request.session_id
        )
    except Exception as e:
        logger.error(f"Failed to clear session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear session: {str(e)}"
        )

# MCP Registry Endpoints
@registry_router.post("/servers", response_model=AddServerResponse)
async def add_server(request: AddServerRequest):
    """Add a new MCP server"""
    try:
        logger.info(f"Adding server: {request.server_config.name}")
        await registry_service.add_server(request.server_config)
        return AddServerResponse(
            success=True,
            message=f"Server '{request.server_config.name}' added successfully",
            server_name=request.server_config.name
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to add server: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add server: {str(e)}"
        )

@registry_router.delete("/servers", response_model=RemoveServerResponse)
async def remove_server(request: RemoveServerRequest):
    """Remove an MCP server"""
    try:
        logger.info(f"Removing server: {request.server_name}")
        await registry_service.remove_server(request.server_name)
        return RemoveServerResponse(
            success=True,
            message=f"Server '{request.server_name}' removed successfully",
            server_name=request.server_name
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to remove server: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove server: {str(e)}"
        )

@registry_router.get("/servers", response_model=ListServersResponse)
async def list_servers():
    """Get list of all registered MCP servers"""
    try:
        servers = await registry_service.list_servers()
        return ListServersResponse(
            success=True,
            servers=servers,
            total_count=len(servers)
        )
    except Exception as e:
        logger.error(f"Failed to list servers: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list servers: {str(e)}"
        )