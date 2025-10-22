"""
call_chain.py

Implements Algorithm 2 from the CONCH paper: assessing and updating the patch
correctness along the entire call chain. This module updates caller functions
based on the return type of the callee and inserts necessary checks and return
statements.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from parser.c_parser import FunctionDecl
from analysis.npd_detector import find_null_dereferences, find_error_positions

@dataclass
class CallChainPatch:
    """Represent a patch in a caller function."""
    file_path: str
    line_number: int
    new_lines: List[str]

class CallChainAnalyzer:
    """
    Analyze and update the entire call chain for a buggy function. Based on the return type,
    update the callers to handle null pointer errors appropriately.
    """

    def __init__(self, call_graph: Dict[str, set], functions: Dict[str, FunctionDecl]):
        self.call_graph = call_graph
        self.functions = functions

    def assess_and_patch(self, buggy_function: FunctionDecl, source_map: Dict[str, List[str]]) -> List[CallChainPatch]:
        """
        Perform call-chain assessment and generate patches for callers.

        :param buggy_function: The function that contains a null pointer dereference.
        :param source_map: Mapping from file paths to list of source lines.
        :return: List of CallChainPatch.
        """
        patches: List[CallChainPatch] = []
        visited = set()

        def recurse(func_name: str):
            if func_name in visited:
                return
            visited.add(func_name)
            for caller, callees in self.call_graph.items():
                if func_name in callees:
                    caller_decl = self.functions.get(caller)
                    if caller_decl:
                        patches.extend(self._patch_caller(caller_decl, buggy_function, source_map))
                        recurse(caller)

        recurse(buggy_function.name)
        return patches

    def _patch_caller(self, caller_decl: FunctionDecl, callee_decl: FunctionDecl,
                      source_map: Dict[str, List[str]]) -> List[CallChainPatch]:
        """
        Generate patches for a caller of the buggy function.

        :param caller_decl: Caller FunctionDecl.
        :param callee_decl: Callee FunctionDecl (buggy).
        :param source_map: Mapping from file paths to list of source lines.
        :return: List of CallChainPatch objects.
        """
        patches: List[CallChainPatch] = []
        src_lines = source_map.get(caller_decl.location[0], [])
        # Find call sites
        for node in caller_decl.body.walk():
            if node.kind == "CallExpr" and node.spelling == callee_decl.name:
                line = node.location[1]
                new_lines: List[str] = []
                # Insert null check based on callee's return type
                if callee_decl.return_type == 'void':
                    # no return value to check; just ensure error does not continue normal execution
                    new_lines.append(f"if (/* error handled in {callee_decl.name} */ false) {{")
                    if caller_decl.return_type == 'void':
                        new_lines.append("    return;")
                    elif caller_decl.return_type.endswith('*'):
                        new_lines.append("    return NULL;")
                    else:
                        new_lines.append("    return -1;")
                    new_lines.append("}")
                else:
                    new_lines.append(f"auto ret_val = {callee_decl.name}();")
                    new_lines.append(f"if (ret_val == NULL) {{")
                    if caller_decl.return_type == 'void':
                        new_lines.append("    return;")
                    elif caller_decl.return_type.endswith('*'):
                        new_lines.append("    return NULL;")
                    else:
                        new_lines.append("    return -1;")
                    new_lines.append("}")
                patches.append(CallChainPatch(file_path=caller_decl.location[0],
                                              line_number=line,
                                              new_lines=new_lines))
        return patches

    def analyze_caller_behavior(self, caller_decl: FunctionDecl, callee_decl: FunctionDecl) -> List[Tuple[int, str]]:
        """
        Analyze how a caller uses the return value of the callee. This can inform where to insert
        additional checks or how to modify the caller's logic. For simplicity, this method returns
        lines where the return value of the callee is used without checking.

        :param caller_decl: Caller function declaration.
        :param callee_decl: Callee function declaration.
        :return: List of tuples (line_number, description).
        """
        uses = []
        if not caller_decl.body:
            return uses
        for node in caller_decl.body.walk():
            if node.kind == "DeclRefExpr" and node.spelling == callee_decl.name:
                uses.append((node.location[1], f"Use of {callee_decl.name} without check"))
        return uses

    def update_call_chain_policy(self, buggy_function: FunctionDecl):
        """
        Placeholder for a more advanced call-chain update policy. In a complete implementation,
        this would consider complex control flows, multiple return paths, and propagate error codes.
        """
        # In a real implementation, one would propagate error codes up the chain.
        pass
