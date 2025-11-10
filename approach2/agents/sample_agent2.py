"""Sample Agent 2 with Registry"""
from agent_framework import ChatAgent
from agent_framework.openai import OpenAIChatClient
from openai import AsyncAzureOpenAI
from config.config import config
from utils.agent_registry import agent_registry, AgentInfo

def create_sample_agent2() -> ChatAgent:
    """Create sports information agent without MCP tools."""
    azure_client = AsyncAzureOpenAI(
        api_key=config.AZURE_OPENAI_KEY,
        api_version=config.AZURE_OPENAI_VERSION,
        azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
    )
    
    return ChatAgent(
        name="SampleAgent2",
        description="A sample test agent for sports information.",
        instructions="You are a sports information specialist.",
        chat_client=OpenAIChatClient(model_id=config.Model, async_client=azure_client),
        tools=[],
    )


# Auto-register
agent_registry.register(AgentInfo(
    name="sample2",
    description="Handles sports information queries",
    capabilities=["sports", "scores"],
    factory=create_sample_agent2,
    requires_mcp=False
))