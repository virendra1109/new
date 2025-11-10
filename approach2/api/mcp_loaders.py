"""Load MCP servers from config on startup."""
from typing import Dict
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from approach2.config.mcp_config import MCP_SERVERS
from approach2.utils.logger_config import magentic_logger


def load_mcp_servers_from_config() -> Dict[str, dict]:
    """
    Load MCP servers from your existing mcp_config.py.

    Supports both 'command'-based and 'http'-based MCP servers.

    Returns:
        Dict of MCP server configurations
    """
    mcp_servers = {}

    for name, config in MCP_SERVERS.items():
        server_type = config.get("type", "command")

        # Handle HTTP-based MCP servers
        if server_type == "http":
            mcp_servers[name] = {
                "name": name,
                "type": "http",
                "url": config["url"],
                "headers": config.get("headers", {}),
                "auth": config.get("auth", None),
            }
            magentic_logger.info(f"Loaded HTTP MCP server: {name} -> {config['url']}")

        # Handle local/CLI command-based MCP servers
        else:
            mcp_servers[name] = {
                "name": name,
                "type": "command",
                "command": config["command"],
                "args": config.get("args", []),
                "env": config.get("env", {}),
            }
            magentic_logger.info(f"Loaded Command MCP server: {name}")

    magentic_logger.info(f"✅ Total MCP servers loaded: {len(mcp_servers)}")
    return mcp_servers


if __name__ == "__main__":
    servers = load_mcp_servers_from_config()
    print("Loaded MCP Servers:")
    for k, v in servers.items():
        print(f" - {k}: {v}")
