"""Version-controlled authority rules for the server-only runtime service."""

from app.agent_runtime.contracts import RuntimeCapability, RuntimeRole

ROLE_CAPABILITIES: dict[RuntimeRole, tuple[RuntimeCapability, ...]] = {
    "orchestrator": (),
    "planner": (),
    "researcher": ("web.search", "web.extract"),
    "reviewer": (),
}

ROLE_TIMEOUT_SECONDS: dict[RuntimeRole, int] = {
    "orchestrator": 60,
    "planner": 60,
    "researcher": 300,
    "reviewer": 120,
}

ALLOWED_HANDOFFS: dict[RuntimeRole, frozenset[RuntimeRole]] = {
    "orchestrator": frozenset(),
    "planner": frozenset({"researcher"}),
    "researcher": frozenset({"reviewer"}),
    "reviewer": frozenset({"researcher"}),
}

MAX_RESEARCH_STEPS = 5
MAX_RESEARCH_ATTEMPTS = 2
