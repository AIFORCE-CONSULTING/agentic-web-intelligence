"""A deterministic LangGraph planner that stops before any agent execution."""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.agent_runtime.contracts import PlanStepProposal, ReviewDecision, RuntimeRun
from app.agent_runtime.service import RuntimePlanError, RuntimeService
from app.web_research.contracts import Evidence, SearchResponse
from app.web_research.mcp_host import GovernedWebMcpHost


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


class ExecutorWorkflowState(TypedDict, total=False):
    """State of one bounded execution after the runtime approval gate."""

    run_id: str
    run: RuntimeRun


class RuntimeExecutionError(RuntimeError):
    """Raised when the deterministic executor cannot complete its bounded work."""


def build_deterministic_executor_workflow(
    service: RuntimeService, host: GovernedWebMcpHost
) -> StateGraph:
    """Build a tool-limited executor that stops at the reviewer boundary."""

    async def execute_research(state: ExecutorWorkflowState) -> ExecutorWorkflowState:
        from uuid import UUID

        run_id = UUID(state["run_id"])
        run = await service.begin_execution(run_id)
        researcher = await service.activate_researcher(run.id)
        try:
            await service.remember_research_query(run.id, researcher.id, run.goal)
            await service.authorize_capability(researcher, "web.search")
            search = await _call_search(host, run.id, researcher.id, run.goal)
            await service.record_tool_outcome(
                run.id,
                researcher.id,
                "web.search",
                {"result_count": len(search.results)},
            )
            if search.results:
                await service.authorize_capability(researcher, "web.extract")
                evidence = await _call_extract(host, run.id, researcher.id, search.results[0].url)
                await service.record_tool_outcome(
                    run.id,
                    researcher.id,
                    "web.extract",
                    {"url": evidence.url, "content_hash": evidence.content_hash},
                )
                await service.remember_source_reference(
                    run.id, researcher.id, evidence.url, evidence.content_hash
                )
        except (RuntimeExecutionError, RuntimePlanError) as error:
            return {"run": await service.fail_research(run.id, researcher.id, str(error))}
        return {"run": await service.complete_research(run.id, researcher.id)}

    return (
        StateGraph(ExecutorWorkflowState)
        .add_node("execute_research", execute_research)
        .add_edge(START, "execute_research")
        .add_edge("execute_research", END)
    )


async def run_deterministic_executor(
    service: RuntimeService, host: GovernedWebMcpHost, run_id: str
) -> RuntimeRun:
    """Execute the stored researcher grant and finish at reviewing or failed."""

    result = await build_deterministic_executor_workflow(service, host).compile().ainvoke(
        {"run_id": run_id}
    )
    return result["run"]


class ReviewWorkflowState(TypedDict, total=False):
    """State for a reviewer that can only inspect persisted run references."""

    run_id: str
    run: RuntimeRun


def _review_decision(run: RuntimeRun) -> ReviewDecision:
    """Evaluate provenance without invoking a model, tool, or external service."""

    if any(memory.memory_type == "source_reference" for memory in run.memories):
        return ReviewDecision(outcome="accepted", reason="Governed source provenance is present.")
    researcher = next(step for step in run.steps if step.role == "researcher")
    if researcher.attempt_count < 2:
        return ReviewDecision(
            outcome="revision_requested",
            reason="No governed source reference was produced; repeat the approved research step.",
        )
    return ReviewDecision(
        outcome="needs_attention",
        reason="No governed source reference was produced within the approved retry budget.",
    )


def build_deterministic_reviewer_workflow(service: RuntimeService) -> StateGraph:
    """Build a no-tool reviewer with one bounded feedback cycle."""

    async def review(state: ReviewWorkflowState) -> ReviewWorkflowState:
        from uuid import UUID

        run_id = UUID(state["run_id"])
        run = await service.get_run(run_id)
        reviewer = await service.activate_reviewer(run.id)
        researcher = next(step for step in run.steps if step.role == "researcher")
        decision = _review_decision(run)
        await service.record_review_decision(run.id, reviewer.id, decision)
        if decision.outcome == "accepted":
            return {"run": await service.accept_review(run.id, reviewer.id)}
        if decision.outcome == "revision_requested":
            return {
                "run": await service.request_research_revision(
                    run.id, reviewer.id, researcher.id, decision.reason
                )
            }
        return {"run": await service.escalate_review(run.id, reviewer.id, decision.reason)}

    return (
        StateGraph(ReviewWorkflowState)
        .add_node("review", review)
        .add_edge(START, "review")
        .add_edge("review", END)
    )


async def run_deterministic_reviewer(service: RuntimeService, run_id: str) -> RuntimeRun:
    """Finish a review or return the run to its single approved revision attempt."""

    result = await build_deterministic_reviewer_workflow(service).compile().ainvoke(
        {"run_id": run_id}
    )
    return result["run"]


async def _call_search(
    host: GovernedWebMcpHost, run_id: object, step_id: object, query: str
) -> SearchResponse:
    result = await _call_tool(
        host,
        f"runtime:{run_id}:{step_id}:search",
        "web.search",
        {"query": query, "max_results": 3},
    )
    return SearchResponse.model_validate(result)


async def _call_extract(
    host: GovernedWebMcpHost, run_id: object, step_id: object, url: str
) -> Evidence:
    result = await _call_tool(
        host,
        f"runtime:{run_id}:{step_id}:extract",
        "web.extract",
        {"url": url},
    )
    return Evidence.model_validate(result)


async def _call_tool(
    host: GovernedWebMcpHost, request_id: str, tool_name: str, arguments: dict[str, object]
) -> dict[str, object]:
    response = await host.handle(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
    )
    result = response.get("result")
    if not isinstance(result, dict) or result.get("isError"):
        raise RuntimeExecutionError(f"The governed {tool_name} call did not succeed.")
    structured = result.get("structuredContent")
    if not isinstance(structured, dict):
        raise RuntimeExecutionError(f"The governed {tool_name} call returned no structured result.")
    return structured
