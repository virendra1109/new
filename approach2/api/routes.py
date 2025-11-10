"""API route handlers."""
from typing import Dict, Union, Optional, Any
from contextlib import AsyncExitStack
import traceback
import sys
import platform
from fastapi import HTTPException
from agent_framework import MCPStdioTool, MCPStreamableHTTPTool, AgentThread

from approach2.api.models import (
    MCPServerConfig, AgentConfig, QueryRequest, 
    QueryResponse, AgentListResponse, MCPServerListResponse,
    ClearSessionRequest, ClearSessionResponse
)
from approach2.api.database import AgentDatabase
from approach2.api.agent_factory import create_agent_instance
from approach2.agents.orchestrator import MagenticOrchestrator
from utils.orchestrator_planner import OrchestratorPlanner
from approach2.utils.agent_indexer import AgentIndexer
from approach2.utils.logger_config import magentic_logger


class APIHandlers:
    """Centralized API request handlers."""
    
    def __init__(self, db: AgentDatabase):
        self.db = db
        self.mcp_servers: Dict[str, dict] = {}
        self.agents_cache: Dict[str, dict] = {}
        self.threads: Dict[str, Any] = {}  # Store threads by session_id
    
    async def initialize(self):
        """Load agents from database on startup."""
        self.agents_cache = self.db.load_all_agents()
    
    def _fix_windows_command(self, command: str, args: list) -> tuple[str, list]:
        """
        Fix command execution on Windows.
        On Windows, batch files like 'npx' need to be run via cmd.exe /c
        """
        if platform.system() == "Windows" and command == "npx":
            # On Windows, npx is a batch file, so we need to run it via cmd.exe
            return "cmd.exe", ["/c", "npx"] + args
        return command, args
    
    # MCP Server Operations
    async def add_mcp_server(self, server: MCPServerConfig) -> dict:
        """Register new MCP server."""
        if server.name in self.mcp_servers:
            raise HTTPException(status_code=400, detail="MCP server already exists")
        
        self.mcp_servers[server.name] = server.dict()
        magentic_logger.info(f"Registered MCP server: {server.name}")
        return {"message": f"MCP server '{server.name}' registered"}
    
    async def list_mcp_servers(self) -> MCPServerListResponse:
        """List all MCP servers."""
        return MCPServerListResponse(
            servers=list(self.mcp_servers.keys()),
            details=self.mcp_servers
        )
    
    async def delete_mcp_server(self, name: str) -> dict:
        """Delete MCP server."""
        if name not in self.mcp_servers:
            raise HTTPException(status_code=404, detail="MCP server not found")
        
        # Check if any agent uses this server
        using_agents = [
            a for a, info in self.agents_cache.items()
            if info.get("mcp_server") == name
        ]
        
        if using_agents:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete: used by agents {using_agents}"
            )
        
        del self.mcp_servers[name]
        magentic_logger.info(f"Deleted MCP server: {name}")
        return {"message": f"MCP server '{name}' deleted"}
    
    # Agent Operations
    async def add_agent(self, agent: AgentConfig) -> dict:
        """Register new agent."""
        if self.db.agent_exists(agent.name):
            raise HTTPException(status_code=400, detail="Agent already exists")
        
        if agent.requires_mcp and agent.mcp_server:
            if agent.mcp_server not in self.mcp_servers:
                raise HTTPException(
                    status_code=400,
                    detail=f"MCP server '{agent.mcp_server}' not found"
                )
        
        agent_data = agent.dict()
        self.db.create_agent(agent_data)
        self.agents_cache[agent.name] = agent_data
        
        magentic_logger.info(f"Registered agent: {agent.name}")
        return {"message": f"Agent '{agent.name}' registered"}
    
    async def list_agents(self) -> AgentListResponse:
        """List all agents."""
        # Refresh from database
        self.agents_cache = self.db.load_all_agents()
        
        return AgentListResponse(
            agents=list(self.agents_cache.keys()),
            details=self.agents_cache
        )
    
    async def get_agent(self, name: str) -> dict:
        """Get agent details."""
        agent = self.db.get_agent(name)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        return agent
    
    async def delete_agent(self, name: str) -> dict:
        """Delete agent."""
        if not self.db.delete_agent(name):
            raise HTTPException(status_code=404, detail="Agent not found")
        
        self.agents_cache.pop(name, None)
        magentic_logger.info(f"Deleted agent: {name}")
        return {"message": f"Agent '{name}' deleted"}
    
    # Query Execution
    async def execute_query(self, request: QueryRequest) -> QueryResponse:
        """Execute query with agent orchestration."""
        query = request.query.strip()
        if not query:
            raise HTTPException(status_code=400, detail="Empty query")
        
        if not self.agents_cache:
            raise HTTPException(status_code=400, detail="No agents registered")
        
        magentic_logger.info(f"\n{'='*70}")
        magentic_logger.info(f"QUERY: {query}")
        if request.session_id:
            magentic_logger.info(f"SESSION: {request.session_id}")
        magentic_logger.info(f"{'='*70}")
        
        try:
            # Get or create thread for session
            thread = self.threads.get(request.session_id) if request.session_id else None
            # Step 1: Agent indexing - semantic selection
            all_agents = {name: info["description"] for name, info in self.agents_cache.items()}
            agent_indexer = AgentIndexer(all_agents)
            selected_agent_names = agent_indexer.search(query, top_k=3)
            
            magentic_logger.info(f"Indexed selection: {', '.join(selected_agent_names)}")
            
            # Step 2: Planner refines selection and generates tool queries
            selected_agents = {name: all_agents[name] for name in selected_agent_names}
            planner = OrchestratorPlanner()
            plan = await planner.plan(query, selected_agents)
            
            # Step 3: Initialize MCP tools for selected agents
            mcp_tools: Dict[str, Union[MCPStdioTool, MCPStreamableHTTPTool]] = {}
            for agent_name in plan["agents"]:
                agent_info = self.agents_cache.get(agent_name)
                if agent_info and agent_info["requires_mcp"]:
                    mcp_config = self.mcp_servers.get(agent_info["mcp_server"])
                    if not mcp_config:
                        raise HTTPException(
                            status_code=500,
                            detail=f"MCP server '{agent_info['mcp_server']}' not configured"
                        )
                    
                    server_type = mcp_config.get("type", "command")
                    magentic_logger.info(f"Initializing MCP for {agent_name} (type: {server_type})...")
                    
                    if server_type == "http":
                        # HTTP-based MCP server
                        mcp_tools[agent_name] = MCPStreamableHTTPTool(
                            name=agent_name,
                            url=mcp_config["url"],
                            headers=mcp_config.get("headers", {}),
                            auth=mcp_config.get("auth"),
                        )
                        magentic_logger.info(f"  Created HTTP MCP tool for {agent_name} -> {mcp_config['url']}")
                    else:
                        # Command-based MCP server (stdio)
                        # Fix Windows command execution (npx needs cmd.exe /c on Windows)
                        command = mcp_config["command"]
                        args = mcp_config.get("args", [])
                        fixed_command, fixed_args = self._fix_windows_command(command, args)
                        
                        mcp_tools[agent_name] = MCPStdioTool(
                            name=agent_name,
                            load_prompts=False,
                            command=fixed_command,
                            args=fixed_args,
                            env=mcp_config.get("env"),
                        )
                        magentic_logger.info(f"  Created Stdio MCP tool for {agent_name} with command: {fixed_command} {' '.join(fixed_args)}")
            
            # Step 4: Create agent instances and execute
            async with AsyncExitStack() as stack:
                for mcp_tool in mcp_tools.values():
                    await stack.enter_async_context(mcp_tool)
                
                agents_dict = {}
                for agent_name in plan["agents"]:
                    agent_info = self.agents_cache[agent_name]
                    tool_query = plan["tool_queries"].get(agent_name)
                    
                    agents_dict[agent_name] = await create_agent_instance(
                        agent_info,
                        mcp_tools.get(agent_name),
                        tool_query
                    )
                
                orchestrator = MagenticOrchestrator()
                orchestrator.build_workflow(agents_dict)
                result = await orchestrator.execute(query, thread=thread)
                
                # Get updated thread if available
                updated_thread = getattr(orchestrator, 'updated_thread', None) or thread
                
                # Store thread if session_id provided
                if request.session_id and updated_thread:
                    self.threads[request.session_id] = updated_thread
                    magentic_logger.info(f"Stored thread for session: {request.session_id}")
                
                magentic_logger.info(f"Execution complete. Agents used: {list(orchestrator.agent_outputs.keys())}")
                
                return QueryResponse(
                    result=result,
                    agents_used=list(orchestrator.agent_outputs.keys()),
                    plan=plan,
                    session_id=request.session_id
                )
        
        except Exception as e:
            error_traceback = traceback.format_exc()
            magentic_logger.error(f"Query execution failed: {e}")
            magentic_logger.error(f"Full traceback:\n{error_traceback}")
            raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")
    
    async def clear_session(self, request: ClearSessionRequest) -> ClearSessionResponse:
        """Clear conversation context for a specific session."""
        if request.session_id in self.threads:
            del self.threads[request.session_id]
            magentic_logger.info(f"Cleared session: {request.session_id}")
            return ClearSessionResponse(
                success=True,
                message=f"Session '{request.session_id}' cleared successfully",
                session_id=request.session_id
            )
        else:
            magentic_logger.warning(f"Session not found: {request.session_id}")
            return ClearSessionResponse(
                success=False,
                message=f"Session '{request.session_id}' not found",
                session_id=request.session_id
            )