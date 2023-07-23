#!/usr/bin/env python3
import sys

class _eval_lhs:
    def __call__(self):
        print("wat, this actually works?")

sys.modules[__name__] = _eval_lhs()
