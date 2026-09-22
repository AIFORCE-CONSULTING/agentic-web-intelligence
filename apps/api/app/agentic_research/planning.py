"""Versioned prompt for the bounded research topic-planning decision."""

TOPIC_PLANNING_PROMPT_VERSION = "agentic-research-topic-plan-v1"

TOPIC_PLANNING_SYSTEM_PROMPT = """You plan focused web research for one operator question.

Break the operator's question into the smallest useful set of focused research topics. Return
between one and three topics. Together, the topics should cover the important parts of the
operator's question without repeating one another.

Return only a JSON array. Every array item must contain exactly these three properties:

- "topic_id": a unique lowercase identifier using words separated by hyphens;
- "topic": a plain-language description of the information this topic needs to find; and
- "search_query": one specific web-search query intended to find evidence for this topic.

The topic_id is a tracking identifier, not a description by itself. Make the topic description
clear enough that another model can later decide whether a webpage supports it. Do not include
Markdown, code fences, commentary, or properties outside the required three."""


def topic_planning_messages(operator_question: str) -> list[dict[str, str]]:
    """Build the fixed system instruction and bounded operator input."""

    question = operator_question.strip()
    if not question:
        raise ValueError("An operator question is required for topic planning.")
    if len(question) > 512:
        raise ValueError("The operator question must not exceed 512 characters.")
    return [
        {"role": "system", "content": TOPIC_PLANNING_SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

