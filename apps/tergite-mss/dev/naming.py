# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Checks that functions are named with a verb and booleans with is_ or should_.

Run from apps/tergite-mss with `python -m dev.naming`. The names that broke these rules
when the check was added are listed in naming_baseline.txt, which may only shrink.
"""
import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Sequence, Set, Tuple, Union

APP_ROOT = Path(__file__).resolve().parent.parent
BASELINE_FILE = Path(__file__).with_name("naming_baseline.txt")
SOURCES = ("api", "services", "utils", "libs", "settings.py")

# a new verb is added here in review, not to the baseline
VERBS = frozenset(
    {
        "accept",
        "add",
        "authenticate",
        "authorize",
        "broadcast",
        "build",
        "cancel",
        "check",
        "choose",
        "cleanup",
        "clear",
        "close",
        "collect",
        "compare",
        "compute",
        "connect",
        "construct",
        "convert",
        "count",
        "create",
        "decode",
        "decrypt",
        "delete",
        "derive",
        "destroy",
        "disconnect",
        "dismiss",
        "dispatch",
        "do",
        "emit",
        "encode",
        "encrypt",
        "ensure",
        "export",
        "extract",
        "fetch",
        "filter",
        "find",
        "forget",
        "format",
        "generate",
        "get",
        "handle",
        "include",
        "increment",
        "index",
        "init",
        "initialize",
        "insert",
        "is",
        "keep",
        "load",
        "log",
        "login",
        "logout",
        "make",
        "map",
        "mark",
        "merge",
        "move",
        "notify",
        "open",
        "order",
        "paginate",
        "parse",
        "partition",
        "patch",
        "pick",
        "prepare",
        "process",
        "publish",
        "pull",
        "push",
        "raise",
        "read",
        "receive",
        "record",
        "register",
        "reject",
        "remove",
        "render",
        "replace",
        "reply",
        "request",
        "require",
        "reset",
        "resolve",
        "restore",
        "route",
        "run",
        "save",
        "search",
        "seed",
        "send",
        "serialize",
        "set",
        "setup",
        "should",
        "sign",
        "sort",
        "split",
        "start",
        "stop",
        "store",
        "switch",
        "sync",
        "toggle",
        "transfer",
        "translate",
        "try",
        "unwrap",
        "update",
        "upsert",
        "use",
        "validate",
        "verify",
        "view",
        "wait",
        "write",
    }
)
HOOK_PREFIX = "on"
BOOLEAN_PREFIXES = ("is_", "should_")
BOOLEAN_ANNOTATIONS = frozenset(
    {"bool", "Optional[bool]", "bool | None", "None | bool"}
)
VALUE_DECORATORS = frozenset({"property", "cached_property", "computed_field"})

FunctionNode = Union[ast.FunctionDef, ast.AsyncFunctionDef]


@dataclass(frozen=True)
class Violation:
    location: str
    rule: str


def main() -> int:
    new, fixed = compare_with_baseline(
        find_violations(APP_ROOT), read_baseline(BASELINE_FILE)
    )
    for violation in new:
        print(f"{violation.location}: {violation.rule}")
    for location in fixed:
        print(f"{location}: fixed; delete it from {BASELINE_FILE.name}")
    return 1 if new or fixed else 0


def find_violations(app_root: Path) -> List[Violation]:
    return [
        violation
        for path in _iter_source_files(app_root)
        for violation in _check_module(path, path.relative_to(app_root).as_posix())
    ]


def read_baseline(path: Path) -> Set[str]:
    lines = path.read_text().splitlines() if path.exists() else []
    return {line.strip() for line in lines if line.strip() and not line.startswith("#")}


def compare_with_baseline(
    violations: Sequence[Violation], baseline: Set[str]
) -> Tuple[List[Violation], List[str]]:
    """Splits out the violations the baseline does not list and the listed ones now fixed"""
    new = [violation for violation in violations if violation.location not in baseline]
    fixed = sorted(baseline - {violation.location for violation in violations})
    return new, fixed


def _iter_source_files(app_root: Path) -> Iterator[Path]:
    for source in SOURCES:
        path = app_root / source
        if path.is_file():
            yield path
        elif path.is_dir():
            yield from sorted(path.rglob("*.py"))


def _check_module(path: Path, relative_path: str) -> Iterator[Violation]:
    tree = ast.parse(path.read_text(), filename=str(path))
    for qualname, node in _walk(tree, prefix=""):
        location = f"{relative_path}::{qualname}"
        if isinstance(node, ast.AnnAssign):
            yield from _check_annotated_name(node, location)
        else:
            yield from _check_function(node, location)


def _walk(node: ast.AST, prefix: str) -> Iterator[Tuple[str, ast.AST]]:
    """Yields every function and annotated name with its dotted qualified name"""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            qualname = f"{prefix}{child.name}"
            if not isinstance(child, ast.ClassDef):
                yield qualname, child
            yield from _walk(child, prefix=f"{qualname}.")
        elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
            yield f"{prefix}{child.target.id}", child
        else:
            yield from _walk(child, prefix)


def _check_function(node: FunctionNode, location: str) -> Iterator[Violation]:
    if not (_is_dunder(node.name) or _is_value(node) or _starts_with_verb(node.name)):
        yield Violation(location, "function name does not start with a verb")

    arguments = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
    for argument in arguments:
        if _is_boolean(argument.annotation) and not _has_boolean_prefix(argument.arg):
            yield Violation(
                f"{location}({argument.arg})",
                "boolean parameter does not start with is_ or should_",
            )


def _check_annotated_name(node: ast.AnnAssign, location: str) -> Iterator[Violation]:
    if _is_boolean(node.annotation) and not _has_boolean_prefix(node.target.id):
        yield Violation(location, "boolean does not start with is_ or should_")


def _is_dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__")


def _is_value(node: FunctionNode) -> bool:
    """Whether a decorator turns the function into a value, which is named as a noun"""
    return any(
        _decorator_name(decorator) in VALUE_DECORATORS
        for decorator in node.decorator_list
    )


def _decorator_name(decorator: ast.expr) -> str:
    target = decorator.func if isinstance(decorator, ast.Call) else decorator
    if isinstance(target, ast.Attribute):
        return target.attr
    return target.id if isinstance(target, ast.Name) else ""


def _starts_with_verb(name: str) -> bool:
    first_word = name.lstrip("_").split("_")[0]
    return first_word in VERBS or first_word == HOOK_PREFIX


def _is_boolean(annotation: ast.expr | None) -> bool:
    return annotation is not None and ast.unparse(annotation) in BOOLEAN_ANNOTATIONS


def _has_boolean_prefix(name: str) -> bool:
    return name.lstrip("_").startswith(BOOLEAN_PREFIXES)


if __name__ == "__main__":
    sys.exit(main())
