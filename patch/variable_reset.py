"""
variable_reset.py

Implements Algorithm 1 from the CONCH paper: resetting global variables and
function arguments when a null pointer dereference is detected. This module
traverses the function to identify variables that need resetting, determines
appropriate reset values, and returns patch modifications.
"""

from dataclasses import dataclass
from typing import List, Tuple, Dict
from parser.c_parser import FunctionDecl
from analysis.npd_detector import find_error_positions

@dataclass
class ResetPatch:
    """Represent a variable reset patch."""
    file_path: str
    line_number: int
    reset_lines: List[str]

class VariableResetter:
    """
    Identify and reset global variables and function arguments in error handling blocks.
    """

    def __init__(self):
        pass

    def _find_globals_and_args(self, function_decl: FunctionDecl) -> Tuple[List[str], List[str]]:
        """
        Identify global variables and function arguments used within the function prior to an error.

        :param function_decl: FunctionDecl object.
        :return: Tuple of lists (global_vars, argument_vars).
        """
        # Placeholder implementation: treat any variable name not defined in parameters as global.
        global_vars = []
        arg_vars = function_decl.parameters.copy()
        local_vars = set()
        for node in function_decl.body.walk():
            if node.kind == "VarDecl":
                local_vars.add(node.spelling)
        for node in function_decl.body.walk():
            if node.kind == "DeclRefExpr":
                name = node.spelling
                if name not in local_vars and name not in arg_vars:
                    global_vars.append(name)
        return (list(set(global_vars)), arg_vars)

    def generate_reset_patches(self, function_decl: FunctionDecl,
                               source_lines: List[str]) -> List[ResetPatch]:
        """
        Create reset patches for global variables and function arguments in the given function.

        :param function_decl: FunctionDecl object.
        :param source_lines: List of source code lines.
        :return: List of ResetPatch objects.
        """
        error_positions = find_error_positions(function_decl)
        if not error_positions:
            return []
        globals_vars, arg_vars = self._find_globals_and_args(function_decl)
        patches: List[ResetPatch] = []
        for err_line in error_positions:
            reset_lines = []
            # Reset arguments to default values (NULL or zero)
            for arg in arg_vars:
                reset_lines.append(f"    {arg} = 0;")
            # Reset global variables
            for g in globals_vars:
                reset_lines.append(f"    {g} = 0;")
            patches.append(ResetPatch(file_path=function_decl.location[0],
                                      line_number=err_line,
                                      reset_lines=reset_lines))
        return patches

    def _determine_default_value(self, var_name: str) -> str:
        """
        Determine an appropriate default value for a variable based on naming conventions.
        This is a naive heuristic: pointer-like names get NULL, numeric-like names get 0.

        :param var_name: Name of the variable.
        :return: String representing the default reset value.
        """
        if '*' in var_name or var_name.lower().endswith('ptr'):
            return "NULL"
        if var_name.lower().startswith(('is_', 'has_')):
            return "false"
        return "0"

    def generate_reset_patches_with_types(self, function_decl: FunctionDecl,
                                          source_lines: List[str]) -> List[ResetPatch]:
        """
        A more sophisticated reset generator that uses type information (if available) to
        reset variables to appropriate values. For demonstration, it falls back to _determine_default_value.

        :param function_decl: FunctionDecl object.
        :param source_lines: List of source lines for context.
        :return: List of ResetPatch objects with typed reset values.
        """
        error_positions = find_error_positions(function_decl)
        if not error_positions:
            return []
        globals_vars, arg_vars = self._find_globals_and_args(function_decl)
        patches: List[ResetPatch] = []
        for err_line in error_positions:
            reset_lines: List[str] = []
            for arg in arg_vars:
                default = self._determine_default_value(arg)
                reset_lines.append(f"    {arg} = {default};")
            for g in globals_vars:
                default = self._determine_default_value(g)
                reset_lines.append(f"    {g} = {default};")
            patches.append(ResetPatch(file_path=function_decl.location[0],
                                      line_number=err_line,
                                      reset_lines=reset_lines))
        return patches
