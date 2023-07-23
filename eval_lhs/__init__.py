#!/usr/bin/env python3
# Code partially from https://lobste.rs/s/xsquae/my_kind_repl
import sys
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
        self.raw_lhs = None
        self._replacable_assert = None

    def generic_visit(self, node):
        super().generic_visit(node)
        if isinstance(node, ast.Assert):
            if not hasattr(node.test, "left"):
                return node
            if not hasattr(node.test, "comparators"):
                return node
            for i, comparator in enumerate(node.test.comparators):
                if not isinstance(comparator, ast.Name):
                    continue
                if comparator.id == __name__:
                    expr_node = ast.Expr(node.test.left)
                    self._replacable_assert = ast.unparse(node)
                    self.raw_lhs = ast.unparse(expr_node)
            return node
        return node


class Replacer(ast.NodeTransformer):
    def __init__(self, replacement):
        self._replacement = replacement
        self._replacement_made = None

    def visit_Assert(self, node):
        if not hasattr(node.test, "comparators"):
            return node
        for i, comparator in enumerate(node.test.comparators):
            if not isinstance(comparator, ast.Name):
                continue
            # If the comparator id matches the module, we've found the target
            # to replace
            if comparator.id == __name__:
                node.test.comparators[i] = ast.Constant(value=self._replacement)
                self._replacement_made = ast.unparse(node)
        return node


def _run_replacement(replacement, prev_globals, prev_locals):
    code_obj = code.compile_command(replacement, symbol="eval")
    return eval(code_obj, prev_globals, prev_locals)


class _EvalLHS:
    """
    When placed on the right-hand side of an "==" comparison, an instance of
    this class will evaluate the left-hand side, replace itself with the
    value that comes from that evaluation, and print it to stdout.

    It is preferred that you use the module name in place of this class for
    convenience.
    """
    def __eq__(self, other):
        caller_frame = getframeinfo(currentframe().f_back)
        calling_filename = caller_frame.filename
        calling_line = caller_frame.lineno # calling line is 1 based
        prev_globals = currentframe().f_back.f_globals
        prev_locals = currentframe().f_back.f_locals
        rewriter = Rewriter()
        with open(calling_filename) as f:
            source = f.read()
            # Parse the syntax tree of the source.
            tree = ast.parse(source)
            # Populate rewriter with the location of this instance of Snapshot.
            new_tree = ast.fix_missing_locations(rewriter.visit(tree))

            # Evaluate the left-hand-side of the "==" for this instance
            replacement = _run_replacement(rewriter.raw_lhs, prev_globals,
                                           prev_locals)

            # The old tree is FUBAR but we now know what we want to replace
            # this instance with.
            lines = source.splitlines()
            tree = ast.parse(source)
            #print(ast.dump(tree, indent=4))
            replacer = Replacer(replacement)
            final_tree = ast.fix_missing_locations(replacer.visit(tree))
            lines[calling_line - 1] = replacer._replacement_made
            print("\n".join(lines))
        return True


sys.modules[__name__] = _EvalLHS()
