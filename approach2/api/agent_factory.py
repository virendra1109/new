"""Dynamic agent instance creation."""
from typing import Optional, List
from agent_framework import ChatAgent
from agent_framework.openai import OpenAIChatClient
from openai import AsyncAzureOpenAI

from approach2.config.config import config
from approach2.utils.faiss_indexers import FAISSToolIndexer


async def create_agent_instance(agent_info: dict, mcp_tool=None, tool_query: Optional[str] = None) -> ChatAgent:
    """
    Dynamically create agent instance from configuration.
    
    Args:
        agent_info: Agent configuration dict
        mcp_tool: MCP tool instance if required
        tool_query: Query for tool filtering
    
    Returns:
        ChatAgent instance
    """
    azure_client = AsyncAzureOpenAI(
        api_key=config.AZURE_OPENAI_KEY,
        api_version=config.AZURE_OPENAI_VERSION,
        azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
    )
    
    tools: List = []
    
    # Filter tools if MCP is required
    if agent_info["requires_mcp"] and mcp_tool:
        all_functions = mcp_tool.functions
        
        if tool_query and all_functions:
            tools_data = [
                {
                    "name": func.name,
                    "description": func.description or func.name,
                    "function": func
                }
                for func in all_functions
            ]
            
            indexer = FAISSToolIndexer(agent_info["name"], tools_data)
            relevant = indexer.search(tool_query, top_k=10)
            tool_names = {t["name"] for t in relevant}
            tools = [t["function"] for t in tools_data if t["name"] in tool_names]
            
            print(f"   {agent_info['name']}: Filtered {len(tools)}/{len(all_functions)} tools")
        else:
            tools = all_functions
            print(f"   {agent_info['name']}: Using all {len(tools)} tools")
    
    return ChatAgent(
        name=agent_info["display_name"],
        description=agent_info["description"],
        instructions=agent_info["instructions"],
        chat_client=OpenAIChatClient(model_id=config.Model, async_client=azure_client),
        tools=tools,
    )