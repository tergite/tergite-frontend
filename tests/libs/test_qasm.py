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
import pytest

from libs.qasm import CircuitInfo, QasmError, read_circuit

_BELL = """OPENQASM 3.0;
include "stdgates.inc";
qubit[2] q;
bit[2] c;
h q[0];
cx q[0], q[1];
c = measure q;
"""
_PULSE = """OPENQASM 3.0;
defcalgrammar "openpulse";
bit[1] c;
cal {
  waveform wf = gaussian(0.5, 100ns, 25ns);
  play(q12_drive, wf);
  c[0] = capture_v1(q12_readout, 2us);
}
"""


@pytest.mark.parametrize(
    "qasm, expected",
    [
        (_BELL, CircuitInfo(num_clbits=2, num_qubits=2, is_pulse_level=False)),
        (
            "OPENQASM 3.0;\nqreg q[3];\ncreg c[3];\ncreg d;\nh $4;\nmeasure q -> c;\n",
            CircuitInfo(num_clbits=4, num_qubits=5, is_pulse_level=False),
        ),
        (
            "OPENQASM 3.0;\ngate mine(a) x, y { rx(a) x; cz x, y; }\n"
            "qubit[2] q;\nbit[2] c;\nmine(0.1) q[0], q[1];\nc = measure q;\n",
            CircuitInfo(num_clbits=2, num_qubits=2, is_pulse_level=False),
        ),
        (_PULSE, CircuitInfo(num_clbits=1, num_qubits=0, is_pulse_level=True)),
    ],
    ids=["bell", "old-registers-and-physical-qubits", "own-gate", "openpulse"],
)
def test_a_circuit_is_read(qasm, expected):
    assert read_circuit(qasm) == expected


@pytest.mark.parametrize(
    "qasm, message, line, column",
    [
        (
            "OPENQASM 3.0;\nqubit[2] q;\nh q[0]\ncx q[0], q[1];\n",
            "missing ';' at 'cx'",
            4,
            1,
        ),
        (
            'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[1];\n',
            'include "qelib1.inc" is not supported; only "stdgates.inc" is',
            2,
            1,
        ),
        (
            "OPENQASM 3.0;\nqubit[1] q;\nbit[1] c;\nmeasure q;\n",
            "a measurement needs a target, e.g. c[0] = measure q[0];",
            4,
            1,
        ),
        (
            "OPENQASM 3.0;\nqubit[1] q;\nbit[1] c = measure q;\n",
            "declare the bits first, then measure into them, e.g. bit[2] c; c = measure q;",
            3,
            1,
        ),
        (
            "OPENQASM 3.0;\nqubit[2] q;\nbit[1] c;\nrx q[0];\nc[0] = measure q[0];\n",
            "rx takes 1 parameter and 1 qubit, but got 0 parameters and 1 qubit",
            4,
            1,
        ),
        (
            "OPENQASM 3.0;\nqubit[2] q;\nbit[1] c;\n  cx q[0];\nc[0] = measure q[0];\n",
            "cx takes 0 parameters and 2 qubits, but got 0 parameters and 1 qubit",
            4,
            3,
        ),
        (
            "OPENQASM 3.0;\nqubit[2] q;\nbit[1] c;\nctrl @ x q[0], q[1];\nc[0] = measure q[0];\n",
            "gate modifiers, as on x, are not supported",
            4,
            1,
        ),
        (
            "OPENQASM 3.0;\nqubit[1] q;\nx q[0];\n",
            "the circuit measures nothing; add e.g. c = measure q;",
            None,
            None,
        ),
    ],
    ids=[
        "syntax",
        "qelib1",
        "measure-without-target",
        "measure-as-initialiser",
        "too-few-parameters",
        "too-few-qubits",
        "modifier",
        "nothing-measured",
    ],
)
def test_a_circuit_the_backends_cannot_run_is_refused_where_it_goes_wrong(
    qasm, message, line, column
):
    with pytest.raises(QasmError) as info:
        read_circuit(qasm)

    assert (info.value.message, info.value.line, info.value.column) == (
        message,
        line,
        column,
    )


def test_a_gate_with_its_own_calibration_is_not_checked_against_the_standard_one():
    qasm = (
        'OPENQASM 3.0;\ndefcalgrammar "openpulse";\n'
        "defcal rx $0 { }\nbit[1] c;\nrx $0;\nc[0] = measure $0;\n"
    )

    assert read_circuit(qasm).is_pulse_level
