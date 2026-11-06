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
"""Reads an OpenQASM 3 circuit as tergite's backends will, and refuses what they cannot run

It parses with `openpulse`, the parser the backends use, and refuses here what a backend would
only report once the job ran, or not at all: a syntax error, an include other than
stdgates.inc, a measurement without a target or as an initialiser, a known gate with the
wrong number of parameters or qubits, a gate modifier, or a circuit that measures nothing.
"""

import dataclasses
from typing import Any, Iterator, List, Optional

import openpulse
from antlr4 import CommonTokenStream, InputStream
from antlr4.error.ErrorListener import ErrorListener
from openpulse import ast as pulse_ast
from openqasm3 import ast

# the backends' gates, and the rest of stdgates.inc they define: name -> (parameters, qubits)
STANDARD_GATES = {
    **dict.fromkeys(("rz", "p", "u1", "phase", "rx", "ry"), (1, 1)),
    **dict.fromkeys(
        ("x", "y", "z", "s", "sdg", "t", "tdg", "sx", "sxdg", "h", "id", "i"), (0, 1)
    ),
    **dict.fromkeys(("u", "U", "u3"), (3, 1)),
    "u2": (2, 1),
    **dict.fromkeys(("cz", "cx", "CX", "swap", "cy", "ch"), (0, 2)),
    **dict.fromkeys(("cp", "cphase", "crx", "cry", "crz"), (1, 2)),
    "cu": (4, 2),
    **dict.fromkeys(("ccx", "cswap"), (0, 3)),
}
ALLOWED_INCLUDE = "stdgates.inc"
CAPTURE_FUNCTIONS = ("capture_v1",)
# openpulse parses `defcal` and `cal` into its own classes, openqasm3 into its
DEFCALS = (ast.CalibrationDefinition, pulse_ast.CalibrationDefinition)
CAL_BLOCKS = (ast.CalibrationStatement, pulse_ast.CalibrationStatement)


class QasmError(ValueError):
    """A circuit the backends cannot run, and where in its text the problem is

    Attributes:
        message: what is wrong, as a sentence
        line: the line, from 1, if known
        column: the column, from 1, if known
    """

    def __init__(
        self, message: str, line: Optional[int] = None, column: Optional[int] = None
    ):
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column


@dataclasses.dataclass(frozen=True)
class CircuitInfo:
    """What a job file and its checks need to know of a circuit

    Attributes:
        num_clbits: the classical bits it declares, which the backend checks exactly
        num_qubits: the qubits it uses, declared or physical ($i)
        is_pulse_level: whether it holds OpenPulse, a `cal` block or a `defcal`
    """

    num_clbits: int
    num_qubits: int
    is_pulse_level: bool


def read_circuit(qasm: str) -> CircuitInfo:
    """Reads an OpenQASM 3 circuit, refusing what the backends cannot run

    Args:
        qasm: the circuit's OpenQASM 3 text, OpenPulse included

    Returns:
        what is needed of the circuit to send it

    Raises:
        QasmError: the circuit is not valid OpenQASM 3, or the backends cannot run it
    """
    _check_syntax(qasm)
    program = _parse(qasm)
    statements = program.statements
    _check_includes(statements)
    gate_arities = {**STANDARD_GATES, **_get_defined_gate_arities(statements)}
    calibrated_gates = {v.name.name for v in statements if isinstance(v, DEFCALS)}
    nodes = list(_get_nodes(program))
    for node in nodes:
        _check_node(node, gate_arities, calibrated_gates)
    if not any(_is_measurement(v) for v in nodes):
        raise QasmError("the circuit measures nothing; add e.g. c = measure q;")

    return CircuitInfo(
        num_clbits=_count_clbits(statements),
        num_qubits=_count_qubits(statements, nodes),
        is_pulse_level=any(isinstance(v, DEFCALS + CAL_BLOCKS) for v in statements),
    )


def _check_syntax(qasm: str) -> None:
    """Refuses text that is not OpenQASM 3, with the line and column of the first error

    openqasm3's own parser raises its error without a message, so the grammar is run here with
    a listener that keeps the message; `cal` blocks are left to `_parse`.
    """
    # openqasm3 keeps its ANTLR grammar in a private module; pyproject pins openqasm3
    from openqasm3._antlr.qasm3Lexer import qasm3Lexer
    from openqasm3._antlr.qasm3Parser import qasm3Parser

    errors = _SyntaxErrors()
    lexer = qasm3Lexer(InputStream(qasm))
    lexer.removeErrorListeners()
    lexer.addErrorListener(errors)
    parser = qasm3Parser(CommonTokenStream(lexer))
    parser.removeErrorListeners()
    parser.addErrorListener(errors)
    parser.program()
    if errors.first is not None:
        raise errors.first


def _parse(qasm: str) -> ast.Program:
    """Parses the text, `cal` blocks as OpenPulse"""
    try:
        return openpulse.parse(qasm)
    except Exception as exp:
        message = str(exp) or type(exp).__name__
        raise QasmError(f"not valid OpenQASM 3 or OpenPulse: {message}")


def _check_includes(statements: List[ast.Statement]) -> None:
    """Refuses any include but stdgates.inc, the one the backends have"""
    for statement in statements:
        if isinstance(statement, ast.Include) and statement.filename != ALLOWED_INCLUDE:
            raise _make_error(
                statement,
                f'include "{statement.filename}" is not supported; '
                f'only "{ALLOWED_INCLUDE}" is',
            )


def _get_defined_gate_arities(statements: List[ast.Statement]) -> dict:
    """The parameters and qubits of each gate the circuit defines itself"""
    return {
        v.name.name: (len(v.arguments), len(v.qubits))
        for v in statements
        if isinstance(v, ast.QuantumGateDefinition)
    }


def _check_node(node: ast.QASMNode, gate_arities: dict, calibrated_gates: set) -> None:
    """Refuses a node the backends would fail on, or silently mis-run"""
    if isinstance(node, ast.QuantumMeasurementStatement) and node.target is None:
        raise _make_error(
            node, "a measurement needs a target, e.g. c[0] = measure q[0];"
        )
    if isinstance(node, ast.ClassicalDeclaration) and isinstance(
        node.init_expression, ast.QuantumMeasurement
    ):
        raise _make_error(
            node,
            "declare the bits first, then measure into them, e.g. bit[2] c; c = measure q;",
        )
    if isinstance(node, ast.QuantumGate):
        _check_gate(node, gate_arities, calibrated_gates)


def _check_gate(
    gate: ast.QuantumGate, gate_arities: dict, calibrated_gates: set
) -> None:
    """Refuses a gate modifier, or a known gate given the wrong parameters or qubits"""
    name = gate.name.name
    if gate.modifiers:
        raise _make_error(gate, f"gate modifiers, as on {name}, are not supported")
    if name in calibrated_gates or name not in gate_arities:
        return
    parameters, qubits = gate_arities[name]
    if (len(gate.arguments), len(gate.qubits)) != (parameters, qubits):
        raise _make_error(
            gate,
            f"{name} takes {_count(parameters, 'parameter')} and "
            f"{_count(qubits, 'qubit')}, but got {_count(len(gate.arguments), 'parameter')} "
            f"and {_count(len(gate.qubits), 'qubit')}",
        )


def _is_measurement(node: ast.QASMNode) -> bool:
    """Whether the node measures a qubit or captures a frame"""
    if isinstance(node, ast.QuantumMeasurementStatement):
        return True
    return (
        isinstance(node, (ast.FunctionCall, pulse_ast.FunctionCall))
        and node.name.name in CAPTURE_FUNCTIONS
    )


def _count_clbits(statements: List[ast.Statement]) -> int:
    """The classical bits declared at the top level, bit[n] and creg alike"""
    total = 0
    for statement in statements:
        if isinstance(statement, ast.ClassicalDeclaration) and isinstance(
            statement.type, ast.BitType
        ):
            total += _get_size(statement, statement.type.size)
    return total


def _count_qubits(statements: List[ast.Statement], nodes: List[ast.QASMNode]) -> int:
    """The qubits used: the declared ones, or up to the highest physical $i if more"""
    declared = sum(
        _get_size(v, v.size) for v in statements if isinstance(v, ast.QubitDeclaration)
    )
    physical = [
        int(v.name[1:]) + 1
        for v in nodes
        if isinstance(v, ast.Identifier) and v.name[1:].isdigit() and v.name[0] == "$"
    ]
    return max([declared, *physical])


def _get_size(node: ast.QASMNode, size: Optional[ast.Expression]) -> int:
    """The size of a declaration: 1 if none is given, else its integer literal"""
    if size is None:
        return 1
    if isinstance(size, ast.IntegerLiteral):
        return size.value
    raise _make_error(node, "register sizes must be whole numbers")


def _get_nodes(node: object) -> Iterator[ast.QASMNode]:
    """Every AST node under the given one, the given one first"""
    if isinstance(node, (ast.QASMNode, pulse_ast.QASMNode)):
        yield node
        for field in dataclasses.fields(node):
            yield from _get_nodes(getattr(node, field.name))
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from _get_nodes(item)


def _make_error(node: ast.QASMNode, message: str) -> QasmError:
    """The error, placed at the node's start"""
    span: Optional[ast.Span] = node.span
    if span is None:
        return QasmError(message)
    return QasmError(message, line=span.start_line, column=span.start_column + 1)


def _count(number: int, noun: str) -> str:
    """The number with its noun, plural unless it is one"""
    return f"{number} {noun}" if number == 1 else f"{number} {noun}s"


class _SyntaxErrors(ErrorListener):
    """Keeps the first syntax error the lexer or parser reports"""

    def __init__(self):
        super().__init__()
        self.first: Optional[QasmError] = None

    def record(
        self,
        recognizer: Any,
        offending_symbol: Any,
        line: int,
        column: int,
        message: str,
        error: Any,
    ) -> None:
        """Records the error, if it is the first"""
        if self.first is None:
            self.first = QasmError(message, line=line, column=column + 1)

    # the name ANTLR calls
    syntaxError = record
