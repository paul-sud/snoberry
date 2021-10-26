from base64 import b64decode, b64encode
from typing import Any, List, Optional, Tuple

# TODO replace with graphql-relay-py https://github.com/graphql-python/graphql-relay-py


def get_cursor_from_offset(offset: int) -> str:
    """
    The arrayconnection:OFFSET cursor is how `graphql-relay-js` does it.
    """
    return b64encode(f"arrayconnection:{offset}".encode()).decode()


def get_offset_from_cursor(cursor: str) -> int:
    """
    Inverse of cursor_from_offset
    """
    return int(b64decode(cursor.encode()).decode().split(":")[-1])


def get_start_and_end_cursor(
    array_length: int, first: Optional[int], after: Optional[str]
) -> Tuple[str, str]:
    """
    Given the array's length and pagination arguments, return the start and end cursors
    needed to populate pageInfo
    """
    start_offset = 0
    if after is not None:
        start_offset = get_offset_from_cursor(after) + 1
    start_cursor = get_cursor_from_offset(start_offset)
    end_offset = array_length - 1
    if first is not None:
        end_offset = start_offset + first - 1
    end_cursor = get_cursor_from_offset(end_offset)
    return start_cursor, end_cursor


def get_edges_to_return(
    all_edges: List[Any], after: Optional[str] = None, first: Optional[int] = None
) -> List[Any]:
    """
    Adapted from Relay cursor spec: https://relay.dev/graphql/connections.htm#
    `before/last` not supported for simplicity.

    EdgesToReturn(allEdges, before, after, first, last)
        Let edges be the result of calling ApplyCursorsToEdges(allEdges, before, after).
        If first is set:
            If first is less than 0:
                Throw an error.
            If edges has length greater than than first:
                Slice edges to be of length first by removing edges from the end of edges.
        If last is set:
            If last is less than 0:
                Throw an error.
            If edges has length greater than than last:
                Slice edges to be of length last by removing edges from the start of edges.
        Return edges.
    """
    edges = apply_cursors_to_edges(all_edges=all_edges, after=after)
    end_index = len(edges)
    if first is not None:
        if first < 0:
            raise ValueError("First should be greater than 0")
        end_index = first
    return edges[:end_index]


def apply_cursors_to_edges(
    all_edges: List[Any], after: Optional[str] = None
) -> List[Any]:
    """
    Adapted from Relay cursor spec: https://relay.dev/graphql/connections.htm#
    `before` not supported for simplicity.

    ApplyCursorsToEdges(allEdges, before, after)
        Initialize edges to be allEdges.
        If after is set:
            Let afterEdge be the edge in edges whose cursor is equal to the after argument.
            If afterEdge exists:
                Remove all elements of edges before and including afterEdge.
        If before is set:
            Let beforeEdge be the edge in edges whose cursor is equal to the before argument.
            If beforeEdge exists:
                Remove all elements of edges after and including beforeEdge.
        Return edges.
    """
    start_index = 0
    if after is not None:
        offset = get_offset_from_cursor(after)
        start_index = offset + 1
    return all_edges[start_index:]


def has_previous_page(
    all_edges: List[Any], after: Optional[str] = None, first: Optional[int] = None
) -> bool:
    """
    HasPreviousPage(allEdges, before, after, first, last)
        If last is set:
            Let edges be the result of calling ApplyCursorsToEdges(allEdges, before, after).
            If edges contains more than last elements return true, otherwise false.
        If after is set:
            If the server can efficiently determine that elements exist prior to after, return true.
        Return false.
    """
    if after is not None:
        offset = get_offset_from_cursor(after)
        return offset != 0
    return False


def has_next_page(
    all_edges: List[Any], after: Optional[str] = None, first: Optional[int] = None
) -> bool:
    """
    HasNextPage(allEdges, before, after, first, last)
        If first is set:
            Let edges be the result of calling ApplyCursorsToEdges(allEdges, before, after).
            If edges contains more than first elements return true, otherwise false.
        If before is set:
            If the server can efficiently determine that elements exist following before, return true.
        Return false.
    """
    if first is not None:
        offset = 0
        if after is not None:
            offset = get_offset_from_cursor(after)
        return len(all_edges) > offset + 1 + first
    return False
