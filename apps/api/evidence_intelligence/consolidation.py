"""Pure grouping policy for bounded summary consolidation."""

from collections.abc import Callable, Sequence
from typing import TypeVar

CONSOLIDATION_POLICY_VERSION = "v1"
MAX_CONSOLIDATION_INPUT_CHARACTERS = 12_000

Item = TypeVar("Item")


def group_within_budget(
    items: Sequence[Item], render: Callable[[Item], str]
) -> tuple[tuple[Item, ...], ...]:
    """Return non-empty ordered groups that each fit the fixed character budget."""

    if not items:
        raise ValueError("At least one summary is required for consolidation.")
    groups: list[tuple[Item, ...]] = []
    current: list[Item] = []
    current_size = 0
    for item in items:
        # Account for the double-newline delimiter used by the fixed renderer.
        size = len(render(item)) + 2
        if size > MAX_CONSOLIDATION_INPUT_CHARACTERS:
            raise ValueError("A summary exceeds the fixed consolidation input budget.")
        if current and current_size + size > MAX_CONSOLIDATION_INPUT_CHARACTERS:
            groups.append(tuple(current))
            current, current_size = [], 0
        current.append(item)
        current_size += size
    if current:
        groups.append(tuple(current))
    return tuple(groups)
