"""MCP Registry Service - Manages MCP server registration"""
from typing import List
import platform
from agent_framework import MCPStdioTool, MCPStreamableHTTPTool
from api.models import MCPServerConfig, ServerInfo
from config.mcp_config import MCP_SERVERS
from utils.faiss_indexers import FAISSToolIndexer
from utils.loggers import logger
from services.agent_service import agent_service

class RegistryService:
    """Service for managing MCP server registry"""
    
    def _fix_windows_command(self, command: str, args: list) -> tuple[str, list]:
        """
        Fix command execution on Windows.
        On Windows, batch files like 'npx' need to be run via cmd.exe /c
        """
        if platform.system() == "Windows" and command == "npx":
            # On Windows, npx is a batch file, so we need to run it via cmd.exe
            return "cmd.exe", ["/c", "npx"] + args
        return command, args
    
    async def add_server(self, config: MCPServerConfig):
        """Add a new MCP server to the registry"""
        if not agent_service.is_initialized():
            raise RuntimeError("Agent not initialized")
        
        # Check if server already exists
        if config.name in agent_service.agent.mcp_connections:
            raise ValueError(f"Server '{config.name}' already exists")
        
        # Validate configuration
        if config.type == "http" and not config.url:
            raise ValueError("HTTP servers require a URL")
        elif config.type == "stdio" and not config.command:
            raise ValueError("Stdio servers require a command")
        
        # Create MCP tool
        if config.type == "http":
            mcp_tool = MCPStreamableHTTPTool(
                name=config.name,
                url=config.url,
            )
        else:
            # Fix Windows command execution (npx needs cmd.exe /c on Windows)
            command = config.command
            args = config.args or []
            fixed_command, fixed_args = self._fix_windows_command(command, args)
            
            mcp_tool = MCPStdioTool(
                name=config.name,
                load_prompts=False,
                command=fixed_command,
                args=fixed_args,
                env=config.env or {},
            )
        
        # Initialize connection
        await mcp_tool.__aenter__()
        
        # Store in agent
        agent_service.agent.mcp_connections[config.name] = mcp_tool
        
        # Index tools
        all_functions = mcp_tool.functions
        if all_functions:
            tools = [
                {
                    "name": func.name,
                    "description": func.description or func.name,
                    "input_schema": getattr(func, "input_schema", {}),
                    "function": func,
                }
                for func in all_functions
            ]
            agent_service.agent.server_tools[config.name] = tools
            agent_service.agent.tool_indexers[config.name] = FAISSToolIndexer(
                config.name, tools
            )
        else:
            agent_service.agent.server_tools[config.name] = []
        
        # Update MCP_SERVERS config for orchestrator
        MCP_SERVERS[config.name] = {
            "type": config.type,
            "command": config.command,
            "args": config.args or [],
            "url": config.url,
            "env": config.env or {},
            "description": config.description or "No description",
        }
        
        logger.info(f"Successfully added server: {config.name}")
    
    async def remove_server(self, server_name: str):
        """Remove an MCP server from the registry"""
        if not agent_service.is_initialized():
            raise RuntimeError("Agent not initialized")
        
        if server_name not in agent_service.agent.mcp_connections:
            raise ValueError(f"Server '{server_name}' not found")
        
        # Disconnect server
        mcp_tool = agent_service.agent.mcp_connections[server_name]
        try:
            await mcp_tool.__aexit__(None, None, None)
        except Exception as e:
            logger.warning(f"Error disconnecting server {server_name}: {e}")
        
        # Remove from agent
        del agent_service.agent.mcp_connections[server_name]
        if server_name in agent_service.agent.server_tools:
            del agent_service.agent.server_tools[server_name]
        if server_name in agent_service.agent.tool_indexers:
            del agent_service.agent.tool_indexers[server_name]
        
        # Remove from MCP_SERVERS config
        if server_name in MCP_SERVERS:
            del MCP_SERVERS[server_name]
        
        logger.info(f"Successfully removed server: {server_name}")
    
    async def list_servers(self) -> List[ServerInfo]:
        """Get list of all registered servers"""
        if not agent_service.is_initialized():
            raise RuntimeError("Agent not initialized")
        
        servers = []
        for name, connection in agent_service.agent.mcp_connections.items():
            tools_count = len(agent_service.agent.server_tools.get(name, []))
            server_config = MCP_SERVERS.get(name, {})
            
            servers.append(ServerInfo(
                name=name,
                type=server_config.get("type", "stdio"),
                description=server_config.get("description"),
                tools_count=tools_count,
                status="active"
            ))
        
        return servers

# Singleton instance
registry_service = RegistryService()