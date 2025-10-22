"""
main.py

CLI entry point for the CONCH-inspired null pointer dereference fixer. This script
orchestrates parsing, analysis, patch generation, call-chain assessment, variable reset,
and applying patches. It can be invoked on a C/C++ project directory or a single file.
"""

import os
import argparse
from typing import Dict, List
from parser.c_parser import CParser
from analysis.npd_detector import find_null_dereferences, find_error_positions
from analysis.context_graph import NPDContextGraph
from analysis.resource_pairs import ResourcePairs
from patch.patch_generator import PatchGenerator
from patch.variable_reset import VariableResetter
from patch.call_chain import CallChainAnalyzer
from patch.patch_applier import PatchApplier

def load_source_files(path: str) -> Dict[str, List[str]]:
    """
    Recursively load C/C++ source files from a directory or a single file.

    :param path: Directory or file path.
    :return: Mapping of file paths to list of lines.
    """
    source_map: Dict[str, List[str]] = {}
    if os.path.isfile(path):
        with open(path, 'r', encoding='utf-8') as f:
            source_map[path] = f.readlines()
    else:
        for root, dirs, files in os.walk(path):
            for f in files:
                if f.endswith(('.c', '.cpp', '.cc', '.h', '.hpp')):
                    full_path = os.path.join(root, f)
                    try:
                        with open(full_path, 'r', encoding='utf-8') as fp:
                            source_map[full_path] = fp.readlines()
                    except (IOError, UnicodeDecodeError):
                        continue
    return source_map

def build_function_map(parser: CParser, source_map: Dict[str, List[str]], compile_args: List[str]) -> Dict[str, object]:
    """
    Build a mapping from function names to FunctionDecl objects across all source files.

    :param parser: CParser instance.
    :param source_map: Mapping of file paths to source lines.
    :param compile_args: Compiler arguments for clang.
    :return: Dictionary mapping function names to FunctionDecl objects.
    """
    functions = {}
    for file_path in source_map.keys():
        try:
            func_decls = parser.parse(file_path, compile_args)
            for fdecl in func_decls:
                functions[fdecl.name] = fdecl
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
    return functions

def main():
    parser = argparse.ArgumentParser(description="Automatic NPD fixer with contextual checks.")
    parser.add_argument("path", help="Path to C/C++ project directory or source file.")
    parser.add_argument("--clang-path", help="Path to libclang shared library.", default=None)
    parser.add_argument("--compile-args", nargs='*', default=[],
                        help="Additional compiler arguments (e.g., include paths).")
    parser.add_argument("--apply", action="store_true", help="Apply patches to files.")
    args = parser.parse_args()

    # Load sources
    source_map = load_source_files(args.path)
    if not source_map:
        print("No source files found.")
        return

    # Initialize parser
    cparser = CParser(clang_library_path=args.clang_path)

    # Build functions
    functions = build_function_map(cparser, source_map, args.compile_args)

    # Build call graph
    call_graph = cparser.build_call_graph(list(functions.values()))

    # Initialize analysis modules
    context_graph = NPDContextGraph()
    resource_pairs = ResourcePairs()
    patch_generator = PatchGenerator(resource_pairs)
    resetter = VariableResetter()
    patch_applier = PatchApplier()
    chain_analyzer = CallChainAnalyzer(call_graph, functions)

    # Generate patches
    all_patches = []
    all_reset_patches = []
    all_chain_patches = []

    for func_name, fdecl in functions.items():
        # Identify dereferences and errors
        derefs = find_null_dereferences(fdecl)
        errors = find_error_positions(fdecl)
        cfg = cparser.build_cfg(fdecl)

        # Build context graph for this function
        context_graph.build_from_function(func_name, derefs, errors, cfg)

        # Generate initial patches
        patches = patch_generator.generate_patches(fdecl, source_map[fdecl.location[0]])
        all_patches.extend(patches)

        # Generate variable reset patches
        reset_patches = resetter.generate_reset_patches(fdecl, source_map[fdecl.location[0]])
        all_reset_patches.extend(reset_patches)

    # Assess call chain patches
    for func_name, fdecl in functions.items():
        # If function has derefs, propagate patch to call chain
        if find_null_dereferences(fdecl):
            chain_patches = chain_analyzer.assess_and_patch(fdecl, source_map)
            all_chain_patches.extend(chain_patches)

    if args.apply:
        updated_sources = patch_applier.apply_patches(source_map,
                                                     all_patches,
                                                     all_reset_patches,
                                                     all_chain_patches)
        # Write updated files
        for fp, lines in updated_sources.items():
            with open(fp + ".patched", 'w', encoding='utf-8') as out:
                out.writelines(lines)
        print("Patches applied and written to *.patched files.")
    else:
        # Preview patches
        print("Generated patches:")
        for p in all_patches:
            print(f"File: {p.file_path}, Line: {p.line_number}")
            for l in p.new_lines:
                print(f"  {l}")
        for rp in all_reset_patches:
            print(f"Reset at {rp.file_path}:{rp.line_number}")
            for l in rp.reset_lines:
                print(f"  {l}")
        for cp in all_chain_patches:
            print(f"Call chain patch at {cp.file_path}:{cp.line_number}")
            for l in cp.new_lines:
                print(f"  {l}")

if __name__ == "__main__":
    main()
