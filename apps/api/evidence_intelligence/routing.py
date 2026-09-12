"""Pure, server-callable routing policy; model output cannot influence it."""

from enum import StrEnum


class ExecutionRoute(StrEnum):
    DIRECT = "direct"
    DURABLE = "durable"


def route_request(source_count: int, total_chunk_count: int) -> ExecutionRoute:
    """Use direct execution only for one source that needs exactly one model call."""

    if source_count < 1 or source_count > 5:
        raise ValueError("A summary request must select from one to five sources.")
    if total_chunk_count < source_count:
        raise ValueError("Every selected source must have at least one chunk.")
    return ExecutionRoute.DIRECT if source_count == total_chunk_count == 1 else ExecutionRoute.DURABLE
