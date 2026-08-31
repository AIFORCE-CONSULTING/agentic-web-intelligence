"""A deterministic LangGraph planner that stops before any agent execution."""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.agent_runtime.contracts import PlanStepProposal, RuntimeRun
from app.agent_runtime.service import RuntimeService


class PlanningWorkflowState(TypedDict, total=False):
    """State carried only inside the trusted server-side planning graph."""

    goal: str
    run: RuntimeRun


def _default_plan(goal: str) -> list[PlanStepProposal]:
    """Return the bounded Phase 3 plan shape without interpreting a model response."""

    return [
        PlanStepProposal(role="researcher", title=f"Gather governed evidence for: {goal}"),
        PlanStepProposal(role="reviewer", title="Review evidence completeness and provenance"),
    ]


def build_deterministic_planning_workflow(service: RuntimeService) -> StateGraph:
    """Build the server-only planner; it always stops at the approval boundary."""

    async def start_run(state: PlanningWorkflowState) -> PlanningWorkflowState:
        return {"run": await service.start_run(state["goal"])}

    async def materialize_plan(state: PlanningWorkflowState) -> PlanningWorkflowState:
        run = state["run"]
        return {"run": await service.approve_plan(run.id, _default_plan(state["goal"]))}

    return (
        StateGraph(PlanningWorkflowState)
        .add_node("start_run", start_run)
        .add_node("materialize_plan", materialize_plan)
        .add_edge(START, "start_run")
        .add_edge("start_run", "materialize_plan")
        .add_edge("materialize_plan", END)
    )


async def run_deterministic_planner(service: RuntimeService, goal: str) -> RuntimeRun:
    """Create an approved runtime plan without tool execution or an LLM call."""

    result = await build_deterministic_planning_workflow(service).compile().ainvoke({"goal": goal})
    return result["run"]
