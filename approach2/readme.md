# Multi-Agent Orchestration System

A FastAPI-based multi-agent orchestration platform that dynamically routes queries to specialized agents with MCP (Model Context Protocol) server integrations.

## What This Does

- **Dynamic Agent Selection**: Uses semantic indexing (FAISS) to select relevant agents based on query
- **MCP Integration**: Connects agents to external services (Slack, HubSpot, Zomato, etc.) via MCP servers
- **Workflow Orchestration**: Coordinates multi-agent collaboration using Magentic framework
- **Hybrid Agent Loading**: Supports both code-based agents and database-stored agents
- **Tool Filtering**: Intelligently filters MCP tools based on query context
- **MLflow Tracking**: Logs all orchestration runs for monitoring

## Architecture

```
Query → Agent Indexer → Planner → Tool Filtering → Magentic Workflow → Result
```

1. **Agent Indexer**: Semantic search to find relevant agents
2. **Planner**: LLM determines which agents and tools needed
3. **Tool Filtering**: FAISS-based filtering of MCP tools per agent
4. **Orchestrator**: Magentic coordinates agent execution

## Project Structure

```
├── app.py                      # FastAPI entry point
├── config/
│   ├── config.py              # Azure OpenAI credentials
│   └── mcp_config.py          # MCP server configurations
├── agents/
│   ├── orchestrator.py        # Magentic workflow coordinator
│   ├── hubspot_agent.py       # HubSpot CRM agent
│   ├── slack_agent.py         # Slack messaging agent
│   └── sample_agent*.py       # Example agents
├── api/
│   ├── routes.py              # API handlers
│   ├── database.py            # Agent persistence
│   ├── agent_factory.py       # Dynamic agent creation
│   ├── agent_loaders.py       # Code + DB agent loading
│   └── mcp_loaders.py         # MCP server initialization
└── utils/
    ├── agent_indexer.py       # FAISS agent selection
    ├── faiss_indexers.py      # Tool filtering
    ├── orchestrator_planner.py # LLM-based planning
    └── logger_config.py       # Logging setup
```

## Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Azure OpenAI
Edit `config/config.py`:
```python
AZURE_OPENAI_KEY = "your-key"
AZURE_OPENAI_ENDPOINT = "your-endpoint"
Model = "gpt-4"
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = "text-embedding-ada-002"
AZURE_OPENAI_VERSION = "2024-02-15-preview"
```

### 3. Configure MCP Servers
Edit `config/mcp_config.py` with your access tokens:
```python
MCP_SERVERS = {
    "slack": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-slack"],
        "env": {
            "SLACK_BOT_TOKEN": "xoxb-your-token",
            "SLACK_TEAM_ID": "T123456"
        }
    },
    "hubspot": {
        "command": "npx",
        "args": ["-y", "@hubspot/mcp-server"],
        "env": {
            "PRIVATE_APP_ACCESS_TOKEN": "your-token"
        }
    }
}
```

### 4. Configure Database (Optional)
Edit `app.py` to add your database connection string:
```python
DATABASE_URL = "postgresql://user:pass@host/db"
```

### 5. Configure MLflow Tracking
Edit `app.py`:
```python
mlflow.set_tracking_uri("file:///path/to/mlflow_tracking")
```

## Running

```bash
python app.py
```

API runs on `http://localhost:8000`

## Usage

### Web Interface
Navigate to `http://localhost:8000` for the UI

### API Endpoints

**Execute Query:**
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Get contacts from HubSpot and post to Slack"}'
```

**List Agents:**
```bash
curl http://localhost:8000/agents
```

**Add Agent:**
```bash
curl -X POST http://localhost:8000/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my_agent",
    "display_name": "MyAgent",
    "description": "Does something",
    "instructions": "You are...",
    "capabilities": ["task1", "task2"],
    "requires_mcp": false
  }'
```

## How It Works

1. **Query arrives** → API receives query
2. **Agent Indexing** → FAISS finds top-3 relevant agents based on descriptions
3. **Planning** → LLM refines selection and generates tool queries per agent
4. **MCP Initialization** → Connects to required MCP servers
5. **Tool Filtering** → FAISS filters tools per agent using tool queries
6. **Workflow Execution** → Magentic orchestrates agents with filtered tools
7. **Result** → Aggregated response returned

## Adding New Agents

Create `agents/your_agent.py`:
```python
from agent_framework import ChatAgent
from utils.agent_registry import agent_registry, AgentInfo

def create_your_agent(mcp_tool=None, tool_query=None):
    return ChatAgent(
        name="YourAgent",
        description="What it does",
        instructions="System prompt",
        chat_client=OpenAIChatClient(...),
        tools=mcp_tool.functions if mcp_tool else []
    )

agent_registry.register(AgentInfo(
    name="your_agent",
    description="Agent description",
    capabilities=["capability1"],
    factory=create_your_agent,
    requires_mcp=True,
    mcp_server="slack"
))
```

Then import in `api/agent_loaders.py`:
```python
import agents.your_agent
```

## Logs

Execution logs saved in `logs/magentic_run_*.log`

## Notes

- FAISS indexes cached in `cache/faiss_indexes/`
- First run builds indexes (slower), subsequent runs use cache
- Each query creates a new MLflow experiment
- Tool filtering reduces context size for better performance