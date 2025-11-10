"""Agent Registry for dynamic agent discovery and management."""
from typing import Dict, List, Callable, Optional
from dataclasses import dataclass


@dataclass
class AgentInfo:
    """Metadata container for agent registration."""
    name: str
    description: str
    capabilities: List[str]
    factory: Callable
    requires_mcp: bool = False
    mcp_server: Optional[str] = None


class AgentRegistry:
    """Central registry for agent discovery and retrieval."""
    
    def __init__(self) -> None:
        self._agents: Dict[str, AgentInfo] = {}
    
    def register(self, info: AgentInfo) -> None:
        """Register an agent with its metadata."""
        self._agents[info.name] = info
        print(f"✓ Registered: {info.name}")
    
    def get_all_agents(self) -> Dict[str, str]:
        """Get all agents as name:description mapping for planning."""
        return {name: info.description for name, info in self._agents.items()}
    
    def get_agent_info(self, name: str) -> Optional[AgentInfo]:
        """Get specific agent metadata by name."""
        return self._agents.get(name)
    
    def list_agents(self) -> List[str]:
        """List all registered agent names."""
        return list(self._agents.keys())


# Global registry instance
agent_registry = AgentRegistry()