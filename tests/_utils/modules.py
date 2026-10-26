# This code is part of Tergite
#
# (C) Copyright Martin Ahindura 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Utility functions for dealing with modules"""
import sys
from typing import List


def remove_modules(module_names: List[str]):
    """Removes all modules whose names start with the given list of modules

    Args:
        module_names: names of modules to remove
    """
    for key in list(sys.modules.keys()):
        if any(key.startswith(name) for name in module_names):
            del sys.modules[key]
