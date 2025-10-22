"""
context_graph.py

Provides the NPDContextGraph class, which is responsible for building a
context graph for Null Pointer Dereference (NPD) analysis. The context graph
captures information about where null pointer dereferences occur, where error
handling statements exist, and the relationship between them through control
and data flow.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict, deque

@dataclass
class GraphNode:
    """Represents a node in the NPD context graph."""
    identifier: str
    kind: str  # e.g., 'null_position', 'error_position', 'statement'
    location: Tuple[str, int]
    successors: Set[str] = field(default_factory=set)

class NPDContextGraph:
    """
    Build and operate on the NPD context graph. Each node represents a statement
    or position relevant to generating patches. Edges capture control flow or
    data flow dependencies.
    """

    def __init__(self):
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: Dict[str, Set[str]] = defaultdict(set)

    def add_node(self, node_id: str, kind: str, location: Tuple[str, int]):
        """Add a node to the graph if it does not already exist."""
        if node_id not in self.nodes:
            self.nodes[node_id] = GraphNode(identifier=node_id, kind=kind, location=location)
        # else, update kind and location if needed

    def add_edge(self, from_id: str, to_id: str):
        """Add a directed edge between two nodes."""
        self.edges[from_id].add(to_id)
        if from_id in self.nodes:
            self.nodes[from_id].successors.add(to_id)

    def build_from_function(self, func_name: str,
                            deref_positions: List[Tuple[str, int]],
                            error_positions: List[int],
                            cfg: Dict[int, List[int]]):
        """
        Construct context graph for a single function based on pointer dereference
        positions, error handling positions, and the control flow graph.

        :param func_name: Name of the function.
        :param deref_positions: List of pointer dereference positions (spelling, line).
        :param error_positions: List of line numbers where error handling statements occur.
        :param cfg: Control flow graph as adjacency list.
        """
        # Add nodes for null positions
        for spelling, line in deref_positions:
            node_id = f"{func_name}_null_{line}"
            self.add_node(node_id, 'null_position', (func_name, line))
        # Add nodes for error positions
        for line in error_positions:
            node_id = f"{func_name}_error_{line}"
            self.add_node(node_id, 'error_position', (func_name, line))
        # Build edges: if there's a path from null position to error handling, connect
        # For simplicity, connect each null to each error that occurs after it in CFG
        for spelling, null_line in deref_positions:
            null_id = f"{func_name}_null_{null_line}"
            visited = set()
            queue = deque([null_line])
            while queue:
                line = queue.popleft()
                if line in error_positions and line > null_line:
                    err_id = f"{func_name}_error_{line}"
                    self.add_edge(null_id, err_id)
                for succ in cfg.get(line, []):
                    if succ not in visited:
                        visited.add(succ)
                        queue.append(succ)

    def get_fix_candidates(self) -> List[Tuple[str, str]]:
        """
        Determine fix candidates based on the context graph. For each null position,
        select an error position along one of its outgoing edges as a candidate fix.
        Returns list of (null_node_id, error_node_id) tuples.
        """
        candidates = []
        for node_id, node in self.nodes.items():
            if node.kind == 'null_position':
                for succ in self.edges.get(node_id, []):
                    # Add candidate if successor is error_position
                    if self.nodes[succ].kind == 'error_position':
                        candidates.append((node_id, succ))
        return candidates

    def summarize_fix_positions(self) -> List[Tuple[str, List[str]]]:
        """
        Summarize distinct fixing position selection policies. This simplified implementation
        groups error positions by their function name. In practice, the policies could be:
        - First error after null,
        - Nearest error,
        - Dominator-based selection,
        - Combined heuristics.
        :return: List of tuples (function_name, [error_positions]).
        """
        grouping: Dict[str, List[str]] = defaultdict(list)
        for node_id, node in self.nodes.items():
            if node.kind == 'error_position':
                func_name = node.location[0]
                grouping[func_name].append(node_id)
        return list(grouping.items())

    def __str__(self):
        """Return a string representation of the context graph."""
        lines = []
        for node_id, node in self.nodes.items():
            lines.append(f"{node_id} ({node.kind}) -> {list(self.edges.get(node_id, []))}")
        return "\\n".join(lines)

    def compute_shortest_paths(self, start_node: str) -> Dict[str, int]:
        """
        Compute the shortest path lengths from a start node to all other nodes in the context graph
        using Breadth-First Search (BFS). The distance represents the number of edges in the shortest path.

        :param start_node: Identifier of the start node.
        :return: Mapping from node identifiers to shortest distance; unreachable nodes will not appear.
        """
        distances: Dict[str, int] = {}
        queue = deque()
        queue.append((start_node, 0))
        visited = set([start_node])
        while queue:
            node_id, dist = queue.popleft()
            distances[node_id] = dist
            for succ in self.edges.get(node_id, []):
                if succ not in visited:
                    visited.add(succ)
                    queue.append((succ, dist + 1))
        return distances

    def select_fix_position_policy(self, null_node_id: str) -> Optional[str]:
        """
        Select a single error position for a given null position based on a simple policy:
        choose the nearest error in terms of shortest path distance. This is a placeholder
        for more complex strategies described in the paper.

        :param null_node_id: Identifier of the null position node.
        :return: Identifier of the selected error position node, or None if none exists.
        """
        if null_node_id not in self.nodes:
            return None
        distances = self.compute_shortest_paths(null_node_id)
        min_dist = float('inf')
        selected = None
        for node_id, dist in distances.items():
            if self.nodes[node_id].kind == 'error_position' and dist > 0 and dist < min_dist:
                min_dist = dist
                selected = node_id
        return selected
