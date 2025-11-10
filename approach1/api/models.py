"""Pydantic models for API requests and responses"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

# Query Models
class QueryRequest(BaseModel):
    query: str = Field(..., description="The query to process", min_length=1)
    session_id: Optional[str] = Field(None, description="Session ID for conversation context")

class QueryResponse(BaseModel):
    success: bool
    query: str
    plan: Dict[str, Any]
    selected_tools: Dict[str, List[str]]
    result: Optional[str] = None
    error: Optional[str] = None
    session_id: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True

# Session Management Models
class ClearSessionRequest(BaseModel):
    session_id: str = Field(..., description="Session ID to clear")

class ClearSessionResponse(BaseModel):
    success: bool
    message: str
    session_id: str

# MCP Server Models
class MCPServerConfig(BaseModel):
    name: str = Field(..., description="Unique server name")
    type: str = Field(default="stdio", description="Server type: 'stdio' or 'http'")
    command: Optional[str] = Field(None, description="Command for stdio servers")
    args: Optional[List[str]] = Field(default_factory=list, description="Arguments for stdio servers")
    url: Optional[str] = Field(None, description="URL for HTTP servers")
    env: Optional[Dict[str, str]] = Field(default_factory=dict, description="Environment variables")
    description: Optional[str] = Field(None, description="Server description")

class AddServerRequest(BaseModel):
    server_config: MCPServerConfig

class AddServerResponse(BaseModel):
    success: bool
    message: str
    server_name: str

class RemoveServerRequest(BaseModel):
    server_name: str

class RemoveServerResponse(BaseModel):
    success: bool
    message: str
    server_name: str

class ServerInfo(BaseModel):
    name: str
    type: str
    description: Optional[str]
    tools_count: int
    status: str

class ListServersResponse(BaseModel):
    success: bool
    servers: List[ServerInfo]
    total_count: int