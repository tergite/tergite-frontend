# This code is part of Tergite
#
# (C) Copyright Martin Ahindura 2023
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Test utilities for numbers"""
from typing import Any


def is_even(number: Any) -> bool:
    """Checks if number is even

    Args:
        number: the number ot check

    Returns:
        True if number is even, False otherwise
    """
    return number % 2 == 0
