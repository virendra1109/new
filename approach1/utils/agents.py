"""Multi-MCP Agent with Orchestrator and Thread Management"""
from typing import Dict, Any, List, Optional
import platform
from agent_framework import MCPStdioTool, MCPStreamableHTTPTool, AgentThread
from config.mcp_config import MCP_SERVERS
from utils.faiss_indexers import FAISSToolIndexer
from utils.orchestrator import OrchestratorAgent


class MultiMCPAgentWithFiltering:
    def __init__(self) -> None:
        self.mcp_connections: Dict[str, Any] = {}
        self.server_tools: Dict[str, List[Dict[str, Any]]] = {}
        self.tool_indexers: Dict[str, FAISSToolIndexer] = {}
        self.orchestrator = OrchestratorAgent()

    def _fix_windows_command(self, command: str, args: list) -> tuple[str, list]:
        """
        Fix command execution on Windows.
        On Windows, batch files like 'npx' need to be run via cmd.exe /c
        """
        if platform.system() == "Windows" and command == "npx":
            # On Windows, npx is a batch file, so we need to run it via cmd.exe
            return "cmd.exe", ["/c", "npx"] + args
        return command, args

    async def initialize(self) -> None:
        """Initialize MCP connections and orchestrator agents"""
        print("Initializing Multi-MCP Agent...")

        for server_name, server_config in MCP_SERVERS.items():
            if server_config.get("type") == "http":
                mcp_tool = MCPStreamableHTTPTool(
                    name=server_name,
                    url=server_config["url"],
                )
            else:
                # Fix Windows command execution (npx needs cmd.exe /c on Windows)
                command = server_config["command"]
                args = server_config.get("args", [])
                fixed_command, fixed_args = self._fix_windows_command(command, args)
                
                mcp_tool = MCPStdioTool(
                    name=server_name,
                    load_prompts=False,
                    command=fixed_command,
                    args=fixed_args,
                    env=server_config.get("env"),
                )

            await mcp_tool.__aenter__()
            self.mcp_connections[server_name] = mcp_tool

            all_functions = mcp_tool.functions
            if not all_functions:
                self.server_tools[server_name] = []
                continue

            tools = [
                {
                    "name": func.name,
                    "description": func.description or func.name,
                    "input_schema": getattr(func, "input_schema", {}),
                    "function": func,
                }
                for func in all_functions
            ]

            self.server_tools[server_name] = tools
            self.tool_indexers[server_name] = FAISSToolIndexer(server_name, tools)

        await self.orchestrator.initialize()
        print("✓ Initialization complete\n")

    async def run(self, query: str, thread: Optional[AgentThread] = None) -> tuple[Any, AgentThread]:
        """Run query with orchestrator planning and execution using thread"""
        print(f"\n{'='*70}\nQUERY: {query}\n{'='*70}")
        
        # Step 1: Orchestrator creates a plan
        plan = await self.orchestrator.plan(query, list(MCP_SERVERS.keys()))
        
        all_filtered_tools = []
        tool_summary = []
        
        # Step 2: Use FAISS to find relevant tools
        for server_name in plan["servers"]:
            if server_name not in self.tool_indexers:
                print(f"Server '{server_name}' not found in indexers")
                continue
            
            tool_query = plan["tool_queries"].get(server_name, query)
            indexer = self.tool_indexers[server_name]
            relevant = indexer.search(tool_query, top_k=5)
            
            print(f"\nSearching {server_name} with: '{tool_query}'")
            print(f"   Found {len(relevant)} tools: {[t['name'] for t in relevant]}")
            
            tool_names = {t["name"] for t in relevant}
            server_tools = [
                t["function"] 
                for t in self.server_tools[server_name] 
                if t["name"] in tool_names
            ]
            all_filtered_tools.extend(server_tools)
            
            if tool_names:
                tool_summary.append(f"  {server_name}: {', '.join(tool_names)}")
        
        print(f"\nSELECTED TOOLS:")
        if tool_summary:
            for line in tool_summary:
                print(line)
        else:
            print("  (none)")

        # Fallback: use all tools if none found
        if not all_filtered_tools:
            print("\n No tools found - executing with ALL tools as fallback")
            for server_name in plan["servers"]:
                if server_name in self.server_tools:
                    all_filtered_tools.extend([t["function"] for t in self.server_tools[server_name]])
            
            if not all_filtered_tools:
                print("No tools available for execution")
                return None, thread

        # Step 3: Execute with filtered tools and thread
        result, updated_thread = await self.orchestrator.execute(query, all_filtered_tools, thread)
        
        print(f"\n{'='*70}\nCOMPLETE\n{'='*70}")
        print(f"\nResponse:\n{result}\n")

        return result, updated_thread

    async def disconnect(self) -> None:
        """Disconnect all servers and shutdown orchestrator"""
        for mcp_tool in self.mcp_connections.values():
            try:
                await mcp_tool.__aexit__(None, None, None)
            except:
                pass
        self.mcp_connections.clear()
        await self.orchestrator.shutdown()