"""Orchestrator Agent for Planning and Execution with Thread Management"""
from typing import Dict, List, Any, Optional
from openai import AsyncAzureOpenAI
from agent_framework import ChatAgent, AgentThread
from agent_framework.openai import OpenAIChatClient
from utils.prompts import *
from config.config import config
from config.mcp_config import MCP_SERVERS
import json


class OrchestratorAgent:
    """Plans server/tool selection AND executes tasks using ChatAgent with thread support"""
    
    def __init__(self):
        azure_client = AsyncAzureOpenAI(
            api_key=config.AZURE_OPENAI_KEY,
            api_version=config.AZURE_OPENAI_VERSION,
            azure_endpoint=config.AZURE_OPENAI_ENDPOINT
        )
        self.openai_client = OpenAIChatClient(
            model_id=config.Model,
            async_client=azure_client
        )
        self.planning_agent: Optional[ChatAgent] = None
        self.execution_agent: Optional[ChatAgent] = None
        
    async def initialize(self):
        """Initialize agents"""
        self.planning_agent = ChatAgent(
            chat_client=self.openai_client,
            name="Planning_Agent",
            instructions=planning_instruction.format(
                server_info="\n".join([
                    f"  - {srv}: {MCP_SERVERS[srv].get('description', 'No description')}"
                    for srv in MCP_SERVERS.keys()
                ])
            )
        )
        
        self.execution_agent = ChatAgent(
            chat_client=self.openai_client,
            name="Execution_Agent",
            instructions=executing_instruction
        )
        
        await self.planning_agent.__aenter__()
        await self.execution_agent.__aenter__()
    
    async def shutdown(self):
        """Shutdown agents"""
        if self.planning_agent:
            await self.planning_agent.__aexit__(None, None, None)
        if self.execution_agent:
            await self.execution_agent.__aexit__(None, None, None)
    
    def decode_json(self, response):
        response_text = str(response)
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            json_str = response_text.split("```")[1].split("```")[0].strip()
        else:
            json_str = response_text.strip()
        return json_str

    async def plan(self, query: str, servers: List[str]) -> Dict:
        """Generate plan with servers and tool queries"""
        response = await self.planning_agent.run(query, tools=[])
        json_str = self.decode_json(response)
        plan = json.loads(json_str)
        
        print(f"\nPLAN:")
        print(f"   Servers: {', '.join(plan['servers'])}")
        for srv, tq in plan['tool_queries'].items():
            print(f"   • {srv}: '{tq}'")
        
        return plan
    
    async def execute(self, query: str, tools: List[Any], thread: Optional[AgentThread] = None) -> Any:
        """Execute query with filtered tools using thread for context"""
        print(f"\nEXECUTING with {len(tools)} tools via ChatAgent Orchestrator.\n")
        
        if thread is None:
            thread = self.execution_agent.get_new_thread()
        
        response = await self.execution_agent.run(query, tools=tools, thread=thread)
        return response, thread