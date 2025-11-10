"""Agent Service - Handles query processing with thread management"""
from typing import Dict, Any, Optional
from utils.agents import MultiMCPAgentWithFiltering
from utils.loggers import logger
from utils.serializers import serialize_agent_response

class AgentService:
    """Service for managing the MCP agent with thread support"""
    
    def __init__(self):
        self.agent: MultiMCPAgentWithFiltering = None
        self._initialized = False
        self.threads: Dict[str, Any] = {}  # Store threads by session_id
    
    async def initialize(self):
        """Initialize the agent"""
        if self._initialized:
            logger.warning("Agent already initialized")
            return
        
        self.agent = MultiMCPAgentWithFiltering()
        await self.agent.initialize()
        self._initialized = True
    
    async def shutdown(self):
        """Shutdown the agent"""
        if self.agent and self._initialized:
            await self.agent.disconnect()
            self._initialized = False
    
    def is_initialized(self) -> bool:
        """Check if agent is initialized"""
        return self._initialized
    
    async def process_query(self, query: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Process query with optional session for context management"""
        if not self._initialized:
            raise RuntimeError("Agent not initialized")
        
        logger.info(f"Processing query: {query} (session: {session_id})")
        
        # Get orchestrator plan
        plan = await self.agent.orchestrator.plan(query, list(self.agent.server_tools.keys()))
        
        # Collect selected tools
        selected_tools = {}
        all_filtered_tools = []
        
        for server_name in plan["servers"]:
            if server_name not in self.agent.tool_indexers:
                continue
            
            tool_query = plan["tool_queries"].get(server_name, query)
            indexer = self.agent.tool_indexers[server_name]
            relevant = indexer.search(tool_query, top_k=5)
            
            tool_names = [t["name"] for t in relevant]
            selected_tools[server_name] = tool_names
            
            server_tool_functions = [
                t["function"]
                for t in self.agent.server_tools[server_name]
                if t["name"] in tool_names
            ]
            all_filtered_tools.extend(server_tool_functions)
        
        # Fallback to all tools if none found
        if not all_filtered_tools:
            logger.warning("No tools found, using all tools as fallback")
            for server_name in plan["servers"]:
                if server_name in self.agent.server_tools:
                    all_filtered_tools.extend([
                        t["function"] 
                        for t in self.agent.server_tools[server_name]
                    ])
        
        # Get or create thread for session
        thread = self.threads.get(session_id) if session_id else None
        
        # Execute with thread
        agent_response, updated_thread = await self.agent.orchestrator.execute(
            query, 
            all_filtered_tools,
            thread=thread
        )
        
        # Store thread if session_id provided
        if session_id:
            self.threads[session_id] = updated_thread
        
        result = serialize_agent_response(agent_response)

        print("sesssion id",session_id)
        return {
            "plan": plan,
            "selected_tools": selected_tools,
            "result": result,
            "session_id": session_id
        }
    
    async def clear_session(self, session_id: str):
        """Clear thread for a specific session"""
        if session_id in self.threads:
            del self.threads[session_id]
            logger.info(f"Cleared session: {session_id}")
    
    async def serialize_thread(self, session_id: str) -> Optional[Dict]:
        """Serialize thread for storage"""
        if session_id in self.threads:
            thread = self.threads[session_id]
            return await thread.serialize()
        return None
    
    async def deserialize_thread(self, session_id: str, serialized_data: Dict):
        """Restore thread from serialized data"""
        thread = await self.agent.orchestrator.execution_agent.deserialize_thread(serialized_data)
        self.threads[session_id] = thread
        logger.info(f"Restored session: {session_id}")

# Singleton instance
agent_service = AgentService()