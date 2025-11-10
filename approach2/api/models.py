"""Pydantic models for FastAPI endpoints."""
from typing import Optional, List, Dict
from pydantic import BaseModel, Field


class MCPServerConfig(BaseModel):
    """MCP Server configuration model."""
    name: str = Field(..., description="Unique server name")
    command: str = Field(..., description="Command to start server")
    args: List[str] = Field(default_factory=list, description="Command arguments")
    env: Optional[Dict[str, str]] = Field(None, description="Environment variables")


class AgentConfig(BaseModel):
    """Agent configuration model."""
    name: str = Field(..., description="Unique agent identifier")
    display_name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Agent description")
    instructions: str = Field(..., description="Agent system instructions")
    capabilities: List[str] = Field(..., description="Agent capabilities")
    requires_mcp: bool = Field(False, description="Whether agent needs MCP server")
    mcp_server: Optional[str] = Field(None, description="MCP server name if required")


class QueryRequest(BaseModel):
    """Query execution request."""
    query: str = Field(..., description="User query to execute")
    session_id: Optional[str] = Field(None, description="Session ID for conversation context")


class QueryResponse(BaseModel):
    """Query execution response."""
    result: str
    agents_used: List[str]
    plan: Dict
    session_id: Optional[str] = None


# Session Management Models
class ClearSessionRequest(BaseModel):
    """Request to clear a session."""
    session_id: str = Field(..., description="Session ID to clear")


class ClearSessionResponse(BaseModel):
    """Response after clearing a session."""
    success: bool
    message: str
    session_id: str


class AgentListResponse(BaseModel):
    """Agent list response."""
    agents: List[str]
    details: Dict[str, dict]


class MCPServerListResponse(BaseModel):
    """MCP server list response."""
    servers: List[str]
    details: Dict[str, dict]