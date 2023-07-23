#!/usr/bin/env python3
# Code partially from https://lobste.rs/s/xsquae/my_kind_repl
from inspect import currentframe, getframeinfo
import uuid
import argparse
import ast
import sys
import code


class Rewriter(ast.NodeTransformer):
    def __init__(self):
        self._replace_lineno = 0
        self._replace_end_lineno = 0
        self._replace_col_offset = 0
        self._replace_end_col_offset = 0
        self._replacement = None
        self._replacable_assert = None
        self._visit_path = []

    def generic_visit(self, node):
        self._visit_path.append(node)
        super().generic_visit(node)
        if isinstance(node, ast.Assert):
            if not hasattr(node.test, "left"):
                return node
            module_node = ast.Expression([], type_ignores=[])
            ast.copy_location(module_node, node)
            expr_node = ast.Expr(node.test.left)
            self._replacable_assert = ast.unparse(node)
            self._replacement = ast.unparse(expr_node)
            return expr_node
        return node

class Replacer(ast.NodeTransformer):
    def __init__(self, replacement):
        self._replacement = replacement
        self._replacement_made = None

    def visit_Assert(self, node):
        if not hasattr(node.test, "comparators"):
            return node
        for i, comparator in enumerate(node.test.comparators):
            if not isinstance(comparator, ast.Call):
                continue
            node.test.comparators[i] = ast.Constant(value=self._replacement)
            self._replacement_made = ast.unparse(node)
            if not isinstance(comparator.func, ast.Name):
                continue
            #node.test.comparators[i] = ast.Constant(69)
            if comparator.func.id == "Snapshot":
                node.test.comparators[i] = ast.Constant(value=self._replacement)
                #sys.stdout.write(ast.unparse(node.comparators[i]))
                return node
        return node

class Snapshot:
    def __init__(self):
        self._expected_value = 0

    def __eq__(self, other):
        caller_frame = getframeinfo(currentframe().f_back)
        calling_filename = caller_frame.filename
        calling_line = caller_frame.lineno # calling line is 1 based
        rewriter = Rewriter()
        with open(calling_filename) as f:
            source = f.read()
            # Parse the syntax tree of the source.
            tree = ast.parse(source)
            # Populate rewriter with the location of this instance of Snapshot.
            new_tree = ast.fix_missing_locations(rewriter.visit(tree))

            # Evaluate the left-hand-side of the "==" for this instance
            prev_globals = currentframe().f_back.f_globals
            prev_locals = currentframe().f_back.f_locals
            code_obj = code.compile_command(rewriter._replacement,
                                            symbol="eval")
            replacement = eval(code_obj, prev_globals, prev_locals)

            # The old tree is FUBAR but we now know what we want to replace
            # this instance with.
            lines = source.splitlines()
            tree = ast.parse(source)
            replacer = Replacer(replacement)
            final_tree = ast.fix_missing_locations(replacer.visit(tree))
            lines[calling_line - 1] = replacer._replacement_made
            print("\n".join(lines))
        return True
