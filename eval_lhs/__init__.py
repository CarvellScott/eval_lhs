#!/usr/bin/env python3
# Code partially from https://lobste.rs/s/xsquae/my_kind_repl
import sys
from inspect import currentframe, getframeinfo
import uuid
import argparse
import ast
import functools
import sys
import code


class Searcher(ast.NodeTransformer):
    """
    This class searches an AST for assertions to replace.
    It does NOT make modifications to the tree.
    """
    def __init__(self, calling_lineno):
        """
        @param calling_lineno (int): The calling line to search.
        """

        self.calling_lineno = calling_lineno
        self.raw_lhs = None

    def visit_Assert(self, node):
        if isinstance(node, ast.Assert):
            if not hasattr(node.test, "left"):
                return node
            if not hasattr(node.test, "comparators"):
                return node
            for i, comparator in enumerate(node.test.comparators):
                if not isinstance(comparator, ast.Name):
                    continue
                if comparator.lineno != self.calling_lineno:
                    continue
                if comparator.id == __name__:
                    self.raw_lhs = ast.unparse(ast.Expr(node.test.left))
            return node
        return node


class Replacer(ast.NodeTransformer):
    """
    This class will replace the right-hand-side of an assertion with a
    previously-calculated value
    """
    def __init__(self, replacement, calling_lineno):
        self._replacement = replacement
        self._replacement_made = None
        self._calling_lineno = calling_lineno

    def visit_Assert(self, node):
        if not hasattr(node.test, "left"):
            return node
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


def _run_replacement(prev_globals, prev_locals, replacement):
    code_obj = code.compile_command(replacement, symbol="eval")
    return eval(code_obj, prev_globals, prev_locals)


class AssertionTransformer(ast.NodeTransformer):
    """
    This class will replace the right-hand-side of an assertion with a
    previously-calculated value
    """
    def __init__(self, replacer_func):
        self._replacer_func = replacer_func
        self._replacement_made = None

    def visit_Assert(self, node):
        if not hasattr(node.test, "left"):
            return node
        if not hasattr(node.test, "comparators"):
            return node
        for i, comparator in enumerate(node.test.comparators):
            if not isinstance(comparator, ast.Name):
                continue
            # If the comparator id matches the module, we've found the target
            # to replace
            if comparator.id == __name__:
                raw_lhs = ast.unparse(ast.Expr(node.test.left))
                value = self._replacer_func(raw_lhs)

                node.test.comparators[i] = ast.Constant(value)
                #self._replacement_made = ast.unparse(node)
                #print(ast.dump(node, indent=4))
        return node


class _EvalLHS:
    """
    When placed on the right-hand side of an "==" comparison, an instance of
    this class will evaluate the left-hand side, replace itself with the
    value that comes from that evaluation, and print it to stdout.

    It is preferred that you use the module name in place of this class for
    convenience.
    """
    def __init__(self):
        self.rewritten_output = None

    def __eq__(self, other):
        caller_frame = getframeinfo(currentframe().f_back)
        calling_filename = caller_frame.filename
        calling_lineno = caller_frame.lineno # calling line is 1 based
        prev_globals = currentframe().f_back.f_globals
        prev_locals = currentframe().f_back.f_locals
        replacer_func = functools.partial(_run_replacement, prev_globals, prev_locals)
        searcher = Searcher(calling_lineno)
        transformer = AssertionTransformer(replacer_func)
        with open(calling_filename) as f:
            source = f.read()
            # Parse the syntax tree of the source.
            tree = ast.parse(source)
            # Populate searcher with the location of this instance of Snapshot.
            post_visit_tree = transformer.visit(tree)


            # Evaluate the left-hand-side of the "==" for this instance

            # Fun trick for your .vimrc:
            # iabbrev eval_lhs eval_lhs<Esc>:w<CR>7Xx:.r !./%<CR>kJ$
            # Then unfalsify this conditional. I should make this a feature
            # somehow.
            if False:
                print(repr(replacement))
                return True

            # The old tree is FUBAR but we now know what we want to replace
            # this instance with.
            lines = source.splitlines()
            tree = ast.parse(source)
            #print(ast.dump(tree, indent=4))
            #replacer = Replacer(replacement, calling_lineno)
            final_tree = ast.fix_missing_locations(post_visit_tree)
            self.rewritten_output = ast.unparse(final_tree)
            #lines[calling_lineno - 1] = replacer._replacement_made
            #print("\n".join(lines))
        return True

    def write(self, filepath):
        with open(filepath, "w") as f:
            print(self.rewritten_output, file=f)



sys.modules[__name__] = _EvalLHS()
