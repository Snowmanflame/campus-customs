"""Customer Service agent: drafts messages to customers. Drafts stay on the board; nothing is sent."""

from pydantic_ai import Agent

from .models import CustomerMessageReport, TeamDeps
from .shared import MODEL, MODEL_SETTINGS, load_prompt, mcp_tools_for

NAME = "customer_service"
TOOLS = frozenset({
    "get_ticket",
    "save_draft_message",
})

customer_service_agent = Agent(
    MODEL,
    name=NAME,
    deps_type=TeamDeps,
    output_type=CustomerMessageReport,
    instructions=load_prompt(NAME),
    toolsets=[mcp_tools_for(NAME, TOOLS)],
    model_settings=MODEL_SETTINGS,
    retries=2,
)
