"""Database operations for agent registry."""
import json
from typing import List, Optional, Dict
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from approach2.utils.logger_config import magentic_logger


class AgentDatabase:
    """Database operations for agent persistence."""
    
    def __init__(self, database_url: str):
        self.engine: Engine = create_engine(database_url, echo=False)
        magentic_logger.info(f"Database connected: {database_url.split('@')[1]}")
    
    def _row_to_dict(self, row) -> dict:
        """Convert database row to agent dictionary."""
        def _load_json(value):
            if value is None:
                return None
            if isinstance(value, (dict, list)):
                return value
            try:
                return json.loads(value)
            except Exception:
                return value
        
        metadata = _load_json(row.get("metadata") or "{}")
        capabilities = _load_json(row.get("capabilities") or "[]")
        instructions = metadata.get("instructions", "") if isinstance(metadata, dict) else ""
        
        return {
            "name": row.get("name"),
            "display_name": row.get("display_name"),
            "description": row.get("description"),
            "instructions": instructions,
            "capabilities": capabilities,
            "requires_mcp": bool(row.get("requires_mcp")),
            "mcp_server": row.get("mcp_server"),
        }
    
    def load_all_agents(self) -> Dict[str, dict]:
        """Load all agents from database."""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT name, display_name, description, requires_mcp, 
                           mcp_server, capabilities, metadata
                    FROM agent_registry
                    ORDER BY created_at DESC
                """))
                rows = result.mappings().all()
            
            agents = {self._row_to_dict(row)["name"]: self._row_to_dict(row) for row in rows}
            magentic_logger.info(f"Loaded {len(agents)} agents from database")
            return agents
        except Exception as e:
            magentic_logger.error(f"Failed to load agents: {e}")
            return {}
    
    def get_agent(self, name: str) -> Optional[dict]:
        """Get single agent by name."""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT name, display_name, description, requires_mcp,
                           mcp_server, capabilities, metadata
                    FROM agent_registry
                    WHERE name = :name
                """), {"name": name})
                row = result.mappings().first()
            
            return self._row_to_dict(row) if row else None
        except Exception as e:
            magentic_logger.error(f"Failed to get agent {name}: {e}")
            return None
    
    def agent_exists(self, name: str) -> bool:
        """Check if agent exists."""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text("SELECT 1 FROM agent_registry WHERE name = :name"),
                    {"name": name}
                )
                return result.first() is not None
        except Exception as e:
            magentic_logger.error(f"Failed to check agent existence: {e}")
            return False
    
    def create_agent(self, agent_data: dict) -> None:
        """Create new agent in database."""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("""
                    INSERT INTO agent_registry
                    (name, display_name, description, factory_ref, requires_mcp, 
                     mcp_server, capabilities, config, status, owner, metadata)
                    VALUES
                    (:name, :display_name, :description, :factory_ref, :requires_mcp,
                     :mcp_server, :capabilities, :config, :status, :owner, :metadata)
                """), {
                    "name": agent_data["name"],
                    "display_name": agent_data["display_name"],
                    "description": agent_data["description"],
                    "factory_ref": None,
                    "requires_mcp": agent_data["requires_mcp"],
                    "mcp_server": agent_data.get("mcp_server"),
                    "capabilities": json.dumps(agent_data["capabilities"]),
                    "config": json.dumps({}),
                    "status": "active",
                    "owner": "api",
                    "metadata": json.dumps({"instructions": agent_data["instructions"]})
                })
                conn.commit()
            
            magentic_logger.info(f"Created agent: {agent_data['name']}")
        except Exception as e:
            magentic_logger.error(f"Failed to create agent: {e}")
            raise
    
    def delete_agent(self, name: str) -> bool:
        """Delete agent from database."""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text("DELETE FROM agent_registry WHERE name = :name"),
                    {"name": name}
                )
                conn.commit()
                deleted = result.rowcount > 0
            
            if deleted:
                magentic_logger.info(f"Deleted agent: {name}")
            return deleted
        except Exception as e:
            magentic_logger.error(f"Failed to delete agent: {e}")
            return False