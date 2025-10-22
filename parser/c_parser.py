"""
c_parser.py

This module provides functionality for parsing C/C++ source files
using the clang.cindex API. It constructs abstract syntax trees (AST),
control flow graphs (CFG) and call graphs to support higher-level analysis.
"""

import os
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

try:
    from clang import cindex
except ImportError:
    # cindex may not be available in the environment. We import inside functions.
    cindex = None

@dataclass
class FunctionDecl:
    """Representation of a function declaration in a source file."""
    name: str
    location: Tuple[str, int]  # (file_path, line_number)
    return_type: str
    parameters: List[str] = field(default_factory=list)
    body: Optional['ASTNode'] = None
    callees: Set[str] = field(default_factory=set)

@dataclass
class ASTNode:
    """Generic AST node wrapper."""
    kind: str
    spelling: str
    location: Tuple[str, int]
    children: List['ASTNode'] = field(default_factory=list)

    def walk(self):
        """Generator for depth-first traversal of the AST."""
        yield self
        for child in self.children:
            yield from child.walk()

class CParser:
    """
    The CParser encapsulates the parsing of C/C++ code into ASTs and call graphs.
    It uses clang's libclang library via clang.cindex.
    """

    def __init__(self, clang_library_path: Optional[str] = None):
        self.index = None
        if clang_library_path:
            cindex.Config.set_library_file(clang_library_path)
        self._ensure_index()

    def _ensure_index(self):
        """Ensure that the clang index is created."""
        global cindex
        if self.index is None:
            if cindex is None:
                # Try to import clang.cindex at runtime
                from clang import cindex as clang_cindex
                cindex = clang_cindex
            self.index = cindex.Index.create()

    def parse(self, file_path: str, compile_args: Optional[List[str]] = None) -> List[FunctionDecl]:
        """
        Parse a C/C++ source file and extract top-level function declarations.

        :param file_path: Path to the source file.
        :param compile_args: Optional list of compiler arguments.
        :return: List of FunctionDecl objects representing the functions in the file.
        """
        self._ensure_index()
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Source file {file_path} does not exist.")
        if compile_args is None:
            compile_args = []

        # Parse the translation unit
        translation_unit = self.index.parse(file_path, args=compile_args)
        functions: List[FunctionDecl] = []

        # Traverse the translation unit to find function declarations
        for cursor in translation_unit.cursor.get_children():
            if cursor.kind.is_declaration() and cursor.kind.name == "FUNCTION_DECL":
                func_decl = self._process_function_decl(cursor)
                if func_decl:
                    functions.append(func_decl)
        return functions

    def _process_function_decl(self, cursor) -> Optional[FunctionDecl]:
        """Process a function declaration cursor and return a FunctionDecl object."""
        name = cursor.spelling
        if not name:
            return None
        location = (cursor.location.file.name, cursor.location.line)
        return_type = cursor.result_type.spelling if cursor.result_type else "void"
        parameters = [arg.spelling for arg in cursor.get_arguments()]
        body = self._build_ast(cursor)
        # Build call relationships
        callees = set()
        for node in body.walk():
            # Find call expressions
            if node.kind == "CallExpr":
                callees.add(node.spelling)
        return FunctionDecl(name=name, location=location,
                            return_type=return_type, parameters=parameters,
                            body=body, callees=callees)

    def _build_ast(self, cursor) -> ASTNode:
        """
        Recursively build an ASTNode tree from a clang cursor.

        :param cursor: The clang cursor.
        :return: ASTNode representing the node and its children.
        """
        node = ASTNode(kind=cursor.kind.name,
                       spelling=cursor.spelling or "",
                       location=(cursor.location.file.name, cursor.location.line))
        for child in cursor.get_children():
            # Only include children from the same file
            try:
                if child.location.file and child.location.file.name == node.location[0]:
                    node.children.append(self._build_ast(child))
            except Exception:
                continue
        return node

    def build_call_graph(self, functions: List[FunctionDecl]) -> Dict[str, Set[str]]:
        """
        Construct a call graph from a list of FunctionDecl objects.

        :param functions: List of FunctionDecl objects.
        :return: Dictionary mapping function names to sets of callee function names.
        """
        graph: Dict[str, Set[str]] = {}
        for func in functions:
            graph[func.name] = func.callees
        return graph

    def build_cfg(self, function_decl: FunctionDecl) -> Dict[int, List[int]]:
        """
        Build a simple CFG for a given function declaration.

        Note: This is a simplified representation where nodes are line numbers,
        and edges connect sequential lines. In practice, you'd need a more
        sophisticated CFG builder (e.g., using pycfg or custom analysis).

        :param function_decl: FunctionDecl to build CFG for.
        :return: CFG represented as adjacency list mapping line numbers to successor lines.
        """
        cfg: Dict[int, List[int]] = {}
        if not function_decl.body:
            return cfg
        lines = [n.location[1] for n in function_decl.body.walk()]
        sorted_lines = sorted(set(lines))
        for i in range(len(sorted_lines) - 1):
            cfg.setdefault(sorted_lines[i], []).append(sorted_lines[i + 1])
        return cfg

    def get_pointer_dereferences(self, function_decl: FunctionDecl) -> List[Tuple[str, int]]:
        """
        Identify potential pointer dereference statements in a function.

        :param function_decl: The FunctionDecl object.
        :return: List of tuples (spelling, line_number) where pointer dereferences occur.
        """
        derefs = []
        for node in function_decl.body.walk():
            # Simple heuristic: look for unary operators and member references with '*' or '->'
            if node.kind in ("UnaryOperator", "MemberRefExpr", "ArraySubscriptExpr"):
                if "*" in node.spelling or "->" in node.spelling:
                    derefs.append((node.spelling, node.location[1]))
        return derefs

    def get_variable_declarations(self, function_decl: FunctionDecl) -> List[Tuple[str, str, int]]:
        """
        Extract all variable declarations within a function along with their types and line numbers.

        :param function_decl: FunctionDecl object representing the function.
        :return: List of tuples (var_name, var_type, line_number).
        """
        declarations: List[Tuple[str, str, int]] = []
        if not function_decl.body:
            return declarations
        for node in function_decl.body.walk():
            if node.kind == "VarDecl":
                # For simplicity, use node.spelling as name and unknown type
                declarations.append((node.spelling, "unknown", node.location[1]))
        return declarations

    def build_full_call_graph(self, functions: List[FunctionDecl]) -> Dict[str, Set[str]]:
        """
        Build a global call graph across multiple source files. This method ensures that
        even indirect or forward declarations are resolved by merging call information from
        all functions.

        :param functions: List of FunctionDecl objects from different files.
        :return: A dictionary mapping function names to sets of callees.
        """
        call_graph: Dict[str, Set[str]] = {}
        for func in functions:
            call_graph.setdefault(func.name, set())
            for callee in func.callees:
                call_graph[func.name].add(callee)
        return call_graph

    def print_function_summary(self, functions: List[FunctionDecl]):
        """
        Print a summary of parsed functions including their names, locations, return types,
        parameters, and called functions. This utility is useful for debugging and analysis.

        :param functions: List of FunctionDecl objects.
        """
        for func in functions:
            print(f"Function: {func.name} at {func.location}")
            print(f"  Return type: {func.return_type}")
            print(f"  Parameters: {func.parameters}")
            print(f"  Callees: {list(func.callees)}")
            print("")
