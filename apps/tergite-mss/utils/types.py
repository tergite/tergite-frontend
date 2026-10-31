# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Some utilities for types"""
import importlib
from typing import Type


def get_class_import_path(cls: Type) -> str:
    """Returns the class import path as a string

    Args:
        cls: the class

    Returns:
        the import path of the class as a string
    """
    return f"{cls.__module__}.{cls.__name__}"


def load_class(cls_path: str) -> Type:
    """Loads a class from an import path

    Args:
        cls_path: the class path

    Returns:
        the imported class
    """
    module_str, class_str = cls_path.rsplit(".", 1)
    module = importlib.import_module(module_str)
    return getattr(module, class_str)
