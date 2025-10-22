"""
npd_detector.py

Module for detecting potential null pointer dereference (NPD) positions
and error-handling statements within functions. This detection is based on
pattern matching within AST nodes derived from a source file.
"""

from typing import List, Tuple
from parser.c_parser import FunctionDecl, ASTNode

def find_null_dereferences(function_decl: FunctionDecl) -> List[Tuple[str, int]]:
    """
    Find potential null pointer dereference positions in a function.

    :param function_decl: FunctionDecl object.
    :return: List of tuples (spelling, line) where dereferences occur.
    """
    derefs = []
    if not function_decl.body:
        return derefs
    for node in function_decl.body.walk():
        # Heuristic: treat '*' or '->' usage as potential dereference
        if node.kind in ("UnaryOperator", "MemberRefExpr", "ArraySubscriptExpr"):
            if "*" in node.spelling or "->" in node.spelling:
                derefs.append((node.spelling, node.location[1]))
    return derefs

def find_error_positions(function_decl: FunctionDecl) -> List[int]:
    """
    Identify lines in a function that correspond to error-handling statements.
    Here we consider 'return', 'goto', or explicit 'if (ptr == NULL)' checks as error handling.

    :param function_decl: FunctionDecl object.
    :return: List of line numbers that are considered error handling.
    """
    errors = []
    if not function_decl.body:
        return errors
    for node in function_decl.body.walk():
        if node.kind == "IfStmt":
            # Very naive: if the condition references a pointer and compares to null
            if "NULL" in node.spelling or "null" in node.spelling.lower():
                errors.append(node.location[1])
        elif node.kind in ("ReturnStmt", "GotoStmt"):
            errors.append(node.location[1])
    return sorted(set(errors))
