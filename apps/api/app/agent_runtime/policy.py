"""Version-controlled authority rules for the server-only runtime service."""

from app.agent_runtime.contracts import (
    AUTHORITY_POLICY_VERSION,
    AuthorizationDecisionReason,
    RuntimeCapability,
    RuntimeRole,
)

POLICY_VERSION = AUTHORITY_POLICY_VERSION

ACTION_RESEARCH_STAGES: dict[RuntimeCapability, frozenset[str]] = {
    "web.search": frozenset({"discovering", "assessing_coverage"}),
    "web.extract": frozenset({"acquiring"}),
}

AUTHORIZATION_EXPLANATIONS: dict[AuthorizationDecisionReason, str] = {
    "allowed": "The stored assignment permits this action for the current research stage.",
    "unknown_action": "The requested action is not an approved research capability.",
    "run_inactive": "The stored research assignment is not active.",
    "step_inactive": "The stored researcher step is not active.",
    "capability_not_granted": "The stored researcher step does not grant this capability.",
    "wrong_workspace": "The assignment does not belong to this workspace.",
    "wrong_research_task": "The assignment does not belong to this research task.",
    "invalid_stage": "This action is not permitted during the current research stage.",
    "resource_out_of_scope": "The requested resource is outside this research task.",
    "source_not_discovered": "The source was not discovered for this research task and topic.",
    "source_limit_exhausted": "The research source limit has been exhausted.",
    "attempt_limit_exhausted": "The source attempt limit has been exhausted.",
    "retry_limit_exhausted": "The request retry limit has been exhausted.",
    "gap_limit_exhausted": "The two permitted missing-topic rounds are exhausted.",
    "human_decision_missing": "A required human evidence decision is missing.",
    "malformed_context": "The capability request is incomplete or malformed.",
    "stale_authorization": "Stored authority changed before the action could execute.",
}


def authorization_explanation(reason: AuthorizationDecisionReason) -> str:
    """Return stable, safe wording for a versioned authority result."""

    return AUTHORIZATION_EXPLANATIONS[reason]

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
# Includes the initial researcher pass. The reviewer can therefore request at
# most two routine revisions without an operator decision.
MAX_RESEARCH_ATTEMPTS = 3

# Exception revisions require an authenticated human operator and reuse the
# already materialized researcher/reviewer assignments.
MAX_OPERATOR_REVISION_APPROVALS = 3
