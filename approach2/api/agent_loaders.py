"""Hybrid agent loader - merges code-based and database agents."""
import sys
import os
from typing import Dict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import agents to trigger auto-registration
import approach2.agents.hubspot_agent
import approach2.agents.slack_agent
import  approach2.agents.sample_agent1
import approach2.agents.sample_agent2

from approach2.utils.agent_registry import agent_registry
from approach2.utils.logger_config import magentic_logger


def load_code_based_agents() -> Dict[str, dict]:
    """
    Load agents that are registered via code (have factory functions).
    These are your working agents from main.py.
    
    Returns:
        Dict mapping agent_name -> agent_info with factory functions
    """
    code_agents = {}
    
    # Get all agents registered in code
    for agent_name in agent_registry.list_agents():
        agent_info = agent_registry.get_agent_info(agent_name)
        if agent_info and agent_info.factory:
            code_agents[agent_name] = {
                "name": agent_name,
                "display_name": agent_info.name,
                "description": agent_info.description,
                "capabilities": agent_info.capabilities,
                "requires_mcp": agent_info.requires_mcp,
                "mcp_server": agent_info.mcp_server,
                "factory": agent_info.factory,  # Important: keep factory reference
                "instructions": "",  # Code-based agents have instructions in factory
            }
            magentic_logger.info(f"Loaded code-based agent: {agent_name}")
    
    magentic_logger.info(f"Total code-based agents: {len(code_agents)}")
    return code_agents


def merge_agents(code_agents: Dict, db_agents: Dict) -> Dict[str, dict]:
    """
    Merge code-based agents with database agents.
    Code-based agents (with factories) take priority.
    
    Args:
        code_agents: Agents from code with factory functions
        db_agents: Agents from database (metadata only)
    
    Returns:
        Merged dict with code agents taking priority
    """
    merged = {}
    
    # First, add all code-based agents (they have factory functions)
    for name, info in code_agents.items():
        merged[name] = info
        merged[name]["source"] = "code"
    
    # Then add database agents that aren't in code
    for name, info in db_agents.items():
        if name not in merged:
            merged[name] = info
            merged[name]["source"] = "database"
            merged[name]["factory"] = None  # DB agents don't have factories
            magentic_logger.info(f"Added database agent: {name}")
    
    magentic_logger.info(f"Total merged agents: {len(merged)} (code: {len(code_agents)}, db: {len(db_agents)})")
    return merged