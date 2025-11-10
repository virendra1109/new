"""Slack Agent with auto-registration and tool filtering."""
from typing import Optional

from agent_framework import ChatAgent
from agent_framework.openai import OpenAIChatClient
from openai import AsyncAzureOpenAI

from config.config import config
from utils.faiss_indexers import FAISSToolIndexer
from utils.agent_registry import agent_registry, AgentInfo


def create_slack_agent(mcp_tool, tool_query: Optional[str] = None) -> ChatAgent:
    """Create Slack agent with filtered tools based on query."""
    azure_client = AsyncAzureOpenAI(
        api_key=config.AZURE_OPENAI_KEY,
        api_version=config.AZURE_OPENAI_VERSION,
        azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
    )
    
    all_functions = mcp_tool.functions
    
    if tool_query and all_functions:
        tools_data = [
            {"name": func.name, "description": func.description or func.name, "function": func}
            for func in all_functions
        ]
        indexer = FAISSToolIndexer("slack", tools_data)
        relevant = indexer.search(tool_query, top_k=5)
        tool_names = {t["name"] for t in relevant}
        filtered_functions = [t["function"] for t in tools_data if t["name"] in tool_names]
        print(f"   Slack: Filtered {len(filtered_functions)}/{len(all_functions)} tools")
    else:
        filtered_functions = all_functions
    
    return ChatAgent(
        name="SlackAgent",
        description="Handles messaging, channels, and users in Slack. Expert in team communication and collaboration tools.",
        instructions="""You are a Slack specialist. ONLY use data provided in conversation. default slack channel is #all-appcino""",
        chat_client=OpenAIChatClient(model_id=config.Model, async_client=azure_client),
        tools=filtered_functions,
    )


# Auto-register agent on import
agent_registry.register(AgentInfo(
    name="slack",
    description="Handles messaging, channels, and users in Slack",
    capabilities=["messaging", "channels", "collaboration"],
    factory=create_slack_agent,
    requires_mcp=True,
    mcp_server="slack"
))