"""Serialization utilities for agent responses"""
from typing import Any, Dict
def serialize_agent_response(response: Any) -> str:
    """
    Serialize AgentRunResponse to a JSON-serializable format.
    
    Args:
        response: AgentRunResponse object from the agent framework
        
    Returns:
        Serializable string representation of the response
    """
    try:
        # Try to extract messages
        if hasattr(response, 'messages') and response.messages:
            messages = []
            for msg in response.messages:
                msg_dict = {
                    "role": getattr(msg, 'role', 'unknown'),
                    "content": getattr(msg, 'content', str(msg))
                }
                
                # Include tool calls if present
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    msg_dict["tool_calls"] = [
                        {
                            "name": getattr(tc, 'name', 'unknown'),
                            "arguments": getattr(tc, 'arguments', {})
                        }
                        for tc in msg.tool_calls
                    ]
                
                messages.append(msg_dict)
            
            # Return the final assistant message content
            assistant_messages = [m for m in messages if m.get('role') == 'assistant']
            if assistant_messages:
                return assistant_messages[-1].get('content', 'No response')
        
        # Try to get content attribute
        if hasattr(response, 'content'):
            return str(response.content)
        
        # Try to get text attribute
        if hasattr(response, 'text'):
            return str(response.text)
        
        # Fallback: convert to string
        return str(response)
        
    except Exception as e:
        return f"Error serializing response: {str(e)}"


def serialize_agent_response_detailed(response: Any) -> Dict[str, Any]:
    """
    Serialize AgentRunResponse to a detailed JSON-serializable format.
    
    Returns a dictionary with all available information.
    """
    result = {
        "response": None,
        "messages": [],
        "tool_calls": [],
        "metadata": {}
    }
    
    try:
        # Extract messages
        if hasattr(response, 'messages') and response.messages:
            for msg in response.messages:
                msg_dict = {
                    "role": getattr(msg, 'role', 'unknown'),
                    "content": getattr(msg, 'content', None)
                }
                
                # Add tool calls
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    for tc in msg.tool_calls:
                        result["tool_calls"].append({
                            "name": getattr(tc, 'name', 'unknown'),
                            "arguments": getattr(tc, 'arguments', {}),
                            "result": getattr(tc, 'result', None)
                        })
                
                result["messages"].append(msg_dict)
            
            # Set final response
            assistant_messages = [m for m in result["messages"] if m.get('role') == 'assistant']
            if assistant_messages:
                result["response"] = assistant_messages[-1].get('content')
        
        # Add metadata
        if hasattr(response, 'usage'):
            result["metadata"]["usage"] = str(response.usage)
        if hasattr(response, 'model'):
            result["metadata"]["model"] = str(response.model)
            
    except Exception as e:
        result["error"] = str(e)
    
    return result