"""Orchestrator Planner for LLM-based agent and tool selection."""
from typing import Dict
import json

from openai import AsyncAzureOpenAI
from approach2.config.config import config


class OrchestratorPlanner:
    """Plans agent and tool selection using LLM analysis."""
    
    def __init__(self) -> None:
        self.client = AsyncAzureOpenAI(
            api_key=config.AZURE_OPENAI_KEY,
            api_version=config.AZURE_OPENAI_VERSION,
            azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
        )
    
    async def plan(self, query: str, available_agents: Dict[str, str]) -> Dict:
        """Determine required agents and their tool queries based on user query."""
        agent_descriptions = "\n".join([
            f"- {name}: {desc}" for name, desc in available_agents.items()
        ])
        
        prompt = f"""Analyze this query and determine which agents are needed:
            Query: {query}

            Available Agents:
            {agent_descriptions}

            Return JSON with:
            1. "agents": list of agent names needed (can be multiple for cross-agent tasks)
            2. "tool_queries": dict mapping each agent to its specific tool search query

            Example for "Get contacts from HubSpot and post to Slack":
            {{
                "agents": ["hubspot", "slack"],
                "tool_queries": {{
                    "hubspot": "search get list contacts email",
                    "slack": "post send message channel"
                }}
            }}

            Return JSON:"""

        response = await self.client.chat.completions.create(
            model=config.Model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        
        plan = json.loads(response.choices[0].message.content)
        print(f"\n{'='*70}")
        print("ORCHESTRATOR PLAN:")
        print(f"   Agents: {', '.join(plan['agents'])}")
        for agent, tq in plan['tool_queries'].items():
            print(f"   {agent}: '{tq}'")
        print(f"{'='*70}\n")
        return plan