"""sample_agent1.py - Weather information agent with auto-registration."""
from agent_framework import ChatAgent
from agent_framework.openai import OpenAIChatClient
from openai import AsyncAzureOpenAI

from config.config import config
from utils.agent_registry import agent_registry, AgentInfo


def create_sample_agent1() -> ChatAgent:
    """Create weather information agent without MCP tools."""
    azure_client = AsyncAzureOpenAI(
        api_key=config.AZURE_OPENAI_KEY,
        api_version=config.AZURE_OPENAI_VERSION,
        azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
    )
    
    return ChatAgent(
        name="SampleAgent1",
        description="A sample test agent for weather information.",
        instructions="You are a weather information specialist.",
        chat_client=OpenAIChatClient(model_id=config.Model, async_client=azure_client),
        tools=[],
    )


# Auto-register
agent_registry.register(AgentInfo(
    name="sample1",
    description="Handles weather information queries",
    capabilities=["weather", "forecasts"],
    factory=create_sample_agent1,
    requires_mcp=False
))
