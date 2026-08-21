"""The first replaceable LangGraph workflow for governed web research."""

from typing import TypedDict

import httpx
from langgraph.graph import END, START, StateGraph

from app.web_research.contracts import Evidence
from app.web_research.extractor import WebExtractor


class ExtractWorkflowState(TypedDict, total=False):
    """State for a single, read-only evidence retrieval run."""

    url: str
    evidence: Evidence


async def retrieve_evidence(state: ExtractWorkflowState) -> ExtractWorkflowState:
    """Invoke the governed extraction implementation, not a raw browser tool."""

    async with httpx.AsyncClient(
        timeout=10.0, headers={"User-Agent": "AgenticWebIntel/0.1"}
    ) as client:
        evidence = await WebExtractor(client).extract(state["url"])
    return {"evidence": evidence}


def build_extract_workflow() -> StateGraph:
    """Build the default orchestration adapter for the Phase 2 extraction slice."""

    return (
        StateGraph(ExtractWorkflowState)
        .add_node("retrieve_evidence", retrieve_evidence)
        .add_edge(START, "retrieve_evidence")
        .add_edge("retrieve_evidence", END)
    )


async def run_extract_workflow(url: str) -> Evidence:
    """Run the workflow and return only its normalized evidence output."""

    result = await build_extract_workflow().compile().ainvoke({"url": url})
    return result["evidence"]
