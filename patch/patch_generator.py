"""
patch_generator.py

Generate initial patches for null pointer dereference by inserting
contextual if checks, retrogressing local resources, and constructing proper
return statements. This module implements the intraprocedural analysis described
in the CONCH paper.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional
from parser.c_parser import FunctionDecl
from analysis.npd_detector import find_null_dereferences, find_error_positions
from analysis.resource_pairs import ResourcePairs

@dataclass
class Patch:
    """Representation of a patch modification."""
    file_path: str
    line_number: int
    original_line: str
    new_lines: List[str]

class PatchGenerator:
    """
    Create patches for functions based on detected null pointer dereferences and
    error-handling positions. It inserts if checks and local resource retrogression.
    """

    def __init__(self, resource_pairs: Optional[ResourcePairs] = None):
        self.resource_pairs = resource_pairs or ResourcePairs()

    def generate_patches(self, function_decl: FunctionDecl, source_lines: List[str]) -> List[Patch]:
        """
        Generate patch objects for a single function.

        :param function_decl: FunctionDecl with AST and call information.
        :param source_lines: List of original source code lines.
        :return: List of Patch objects.
        """
        patches: List[Patch] = []
        derefs = find_null_dereferences(function_decl)
        error_positions = find_error_positions(function_decl)
        missing_resources = self.resource_pairs.find_missing_releases(function_decl)

        for deref, line in derefs:
            # Determine the error position for this deref (choose first error after it)
            error_line = None
            for err_line in error_positions:
                if err_line > line:
                    error_line = err_line
                    break
            if error_line is None:
                # If no error handling, choose to insert before dereference
                error_line = line
            # Build if condition: check if pointer is null and handle
            pointer_name = deref.replace('*', '').replace('->', '.').strip()
            condition = f"if ({pointer_name} == NULL) {{"
            new_code = [condition]
            # Insert resource retrogression
            for acquire_func, acq_line in missing_resources:
                if acq_line < line:
                    release_func = self.resource_pairs.get_release(acquire_func)
                    if release_func:
                        new_code.append(f"    {release_func}({pointer_name});")
            # Construct return statement
            if function_decl.return_type == 'void':
                new_code.append("    return;")
            elif function_decl.return_type.endswith('*'):
                new_code.append("    return NULL;")
            else:
                new_code.append("    return -1;")
            new_code.append("}")
            original_line = source_lines[line - 1] if 0 <= line - 1 < len(source_lines) else ""
            patches.append(Patch(file_path=function_decl.location[0],
                                 line_number=line,
                                 original_line=original_line,
                                 new_lines=new_code))
        return patches
