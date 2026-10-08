"""Model, prompts, and the MCP connection shared by every agent.

All agents run on gpt-6-luna through the Portkey AI gateway (OpenAI Responses
API) and reach the database only through the campus-customs MCP server
described in .mcp.json. The Portkey key is read from the local, git-ignored
.env file at the project root and is only ever sent to Portkey.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

from fastmcp import Client
from pydantic_ai import AbstractToolset
from pydantic_ai.mcp import MCPToolset
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.openai import OpenAIProvider

ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
MCP_CONFIG = ROOT / ".mcp.json"
ORIGINAL_DB = ROOT / "data" / "campus_customs.db"
WORKING_DB = ROOT / "data" / "campus_customs_new.db"



def _load_local_env(path: Path = ROOT / ".env") -> None:
    """Read KEY=VALUE lines from the local .env into os.environ (real env vars win)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_local_env()

PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
MODEL_NAME = "gpt-6-luna"


def portkey_key() -> str | None:
    return os.environ.get("PORTKEY_API_KEY")


def _build_model() -> OpenAIResponsesModel:
    # gpt-6-luna (Azure OpenAI behind Portkey) only allows function tools with
    # reasoning on the Responses API, so every agent uses OpenAIResponsesModel.
    key = portkey_key() or "missing-portkey-key"
    client = AsyncOpenAI(
        base_url=PORTKEY_BASE_URL,
        api_key=key,
        default_headers={
            "x-portkey-api-key": key,
            # Never serve agents a cached answer: every run must be a fresh decision, and
            # cached Responses items carry 'portkey_cache_*' ids that Azure rejects on the next turn.
            "x-portkey-cache-force-refresh": "true",
        },
    )
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


MODEL = _build_model()
MODEL_SETTINGS = OpenAIResponsesModelSettings(
    max_tokens=16000,
    openai_reasoning_effort="medium",
)

# Tools only a human (via the dashboard/backend) may call. Never given to an agent.
HUMAN_ONLY_TOOLS = frozenset({"approve_and_pay", "reject_payment", "approve_purchase_order"})


def load_prompt(agent_name: str) -> str:
    return (PROMPTS_DIR / f"{agent_name}.md").read_text(encoding="utf-8")


def mcp_config() -> dict:
    """.mcp.json with machine-specific bits filled in, so a fresh clone works anywhere:
    run the server with this same Python (the one that has fastmcp installed) and
    resolve relative paths against the project root."""
    cfg = json.loads(MCP_CONFIG.read_text())
    for server in cfg["mcpServers"].values():
        server["command"] = sys.executable
        server["args"] = [str(ROOT / a) if a.endswith(".py") else a for a in server.get("args", [])]
        env = server.setdefault("env", {})
        if "CAMPUS_DB" in env and not Path(env["CAMPUS_DB"]).is_absolute():
            env["CAMPUS_DB"] = str(ROOT / env["CAMPUS_DB"])
    return cfg


def _mcp_client() -> Client:
    return Client(mcp_config())


# One MCP connection shared by the whole team (MCPToolset is reference-counted,
# so nested agent runs reuse the same server process).
CAMPUS_MCP = MCPToolset(_mcp_client(), id="campus-customs")


def mcp_tools_for(agent_name: str, allowed: frozenset[str]) -> AbstractToolset:
    """The slice of MCP tools one agent is allowed to see."""
    leaked = allowed & HUMAN_ONLY_TOOLS
    if leaked:
        raise ValueError(f"{agent_name} must not get human-only tools: {sorted(leaked)}")
    return CAMPUS_MCP.filtered(lambda ctx, tool_def: tool_def.name in allowed)


# Connection for orchestration code (backend routes, ticket loop). The FastMCP
# Client is reentrant: the FastAPI app holds it open for its lifetime, and
# each mcp_call just reuses that session.
BACKEND_MCP = _mcp_client()


async def mcp_call(tool: str, **args):
    """Direct MCP call for orchestration code (not agents), e.g. listing open tickets."""
    async with BACKEND_MCP as client:
        result = await client.call_tool(tool, args)
    return result.structured_content if result.structured_content is not None else result.data


def reset_database() -> None:
    """Copy the original database over the working copy. Call before every full run."""
    shutil.copyfile(ORIGINAL_DB, WORKING_DB)
