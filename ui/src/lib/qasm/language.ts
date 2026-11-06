/**
 * OpenQASM 3 for the code editor: highlighting, and completion of what a circuit is made of.
 *
 * Highlighting is a small stream tokenizer, enough for colour; MSS parses the circuit for real
 * when it is run, and its errors are shown in the editor.
 */
import {
  type Completion,
  type CompletionContext,
  type CompletionResult,
  snippetCompletion,
} from "@codemirror/autocomplete";
import {
  HighlightStyle,
  StreamLanguage,
  type StreamParser,
  type StringStream,
} from "@codemirror/language";
import { tags } from "@lezer/highlight";

const KEYWORDS = [
  "OPENQASM", "include", "defcalgrammar", "gate", "def", "defcal", "cal",
  "qubit", "qreg", "bit", "creg", "measure", "reset", "barrier", "delay",
  "if", "else", "for", "while", "in", "return", "let", "const", "input",
  "output", "box", "extern", "ctrl", "negctrl", "inv", "pow",
];
const TYPES = [
  "int", "uint", "float", "angle", "bool", "duration", "stretch", "complex",
  "waveform", "port", "frame", "array",
];
// stdgates.inc and the backends' own gates: name -> [parameters, qubits]
const GATES: Record<string, [number, number]> = {
  h: [0, 1], x: [0, 1], y: [0, 1], z: [0, 1], s: [0, 1], sdg: [0, 1],
  t: [0, 1], tdg: [0, 1], sx: [0, 1], sxdg: [0, 1], id: [0, 1],
  rx: [1, 1], ry: [1, 1], rz: [1, 1], p: [1, 1], u1: [1, 1], phase: [1, 1],
  u2: [2, 1], u: [3, 1], u3: [3, 1],
  cx: [0, 2], cy: [0, 2], cz: [0, 2], ch: [0, 2], swap: [0, 2],
  cp: [1, 2], crx: [1, 2], cry: [1, 2], crz: [1, 2], cu: [4, 2],
  ccx: [0, 3], cswap: [0, 3],
};
// OpenPulse's functions, as the backends take them inside cal blocks
const PULSE_FUNCTIONS = [
  "play", "capture_v1", "shift_phase", "set_phase", "shift_frequency",
  "set_frequency", "gaussian", "gaussian_square", "drag", "sech", "constant",
  "sine",
];
const CONSTANTS = ["pi", "π", "tau", "τ", "euler", "ℇ", "true", "false"];
const WORD_TYPES: Record<string, string> = Object.fromEntries([
  ...KEYWORDS.map((word) => [word, "keyword"]),
  ...TYPES.map((word) => [word, "typeName"]),
  ...Object.keys(GATES).map((word) => [word, "function"]),
  ...PULSE_FUNCTIONS.map((word) => [word, "function"]),
  ...CONSTANTS.map((word) => [word, "atom"]),
]);
const NUMBER = /^(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?(?:ns|us|µs|ms|s|dt)?/;
// letters, digits and _, plus the constants π, τ and ℇ OpenQASM spells as symbols
const IDENTIFIER = /^[A-Za-z_πτℇ][\w]*/;
const PHYSICAL_QUBIT = /^\$\d+/;
const OPERATOR = /^(?:->|==|!=|<=|>=|&&|\|\||<<|>>|\*\*|[-+*/%=<>!~&|^@])/;

export const QASM_LANGUAGE = StreamLanguage.define<QasmState>(createParser());

/** Colours for the tokens, from the theme's --code-* variables so they follow dark mode */
export const QASM_HIGHLIGHT = HighlightStyle.define([
  { tag: tags.keyword, color: "hsl(var(--code-keyword))" },
  { tag: tags.typeName, color: "hsl(var(--code-type))" },
  { tag: tags.function(tags.variableName), color: "hsl(var(--code-gate))" },
  { tag: [tags.number, tags.atom], color: "hsl(var(--code-number))" },
  { tag: tags.string, color: "hsl(var(--code-string))" },
  {
    tag: [tags.lineComment, tags.blockComment],
    color: "hsl(var(--code-comment))",
    fontStyle: "italic",
  },
]);

/** A new circuit: a Bell pair, measured */
export const BELL_CIRCUIT = `OPENQASM 3.0;
include "stdgates.inc";

qubit[2] q;
bit[2] c;

h q[0];
cx q[0], q[1];
c = measure q;
`;

/**
 * Makes the completion source for a device: keywords, types, gates with their arity, the
 * device's frames inside cal blocks, and starter snippets
 *
 * @param numberOfQubits - the device's qubits, offered as a register size
 * @param frames - the device's frames, e.g. q12_drive, if any
 * @returns the completion source
 */
export function makeQasmCompletions(numberOfQubits: number, frames: string[]) {
  const options: Completion[] = [
    ...KEYWORDS.map((label) => ({ label, type: "keyword" })),
    ...TYPES.map((label) => ({ label, type: "type" })),
    ...Object.entries(GATES).map(([label, [parameters, qubits]]) => ({
      label,
      type: "function",
      detail: formatArity(parameters, qubits),
    })),
    ...PULSE_FUNCTIONS.map((label) => ({ label, type: "function", detail: "OpenPulse" })),
    ...frames.map((label) => ({ label, type: "variable", detail: "frame" })),
    snippetCompletion('include "stdgates.inc";', { label: "include stdgates", type: "keyword" }),
    snippetCompletion(`qubit[${numberOfQubits}] \${q};`, {
      label: `qubit[${numberOfQubits}]`,
      type: "keyword",
      detail: "all qubits",
    }),
    snippetCompletion("c = measure q;", { label: "measure all", type: "keyword" }),
    snippetCompletion(BELL_CIRCUIT, { label: "bell", type: "text", detail: "circuit" }),
    snippetCompletion(makeGhzCircuit(numberOfQubits), {
      label: "ghz",
      type: "text",
      detail: "circuit",
    }),
  ];

  return (context: CompletionContext): CompletionResult | null => {
    const word = context.matchBefore(/[\w$]+/);
    if (!word || (word.from === word.to && !context.explicit)) {
      return null;
    }
    return { from: word.from, options, validFor: /^[\w$]*$/ };
  };
}

type QasmState = { isInBlockComment: boolean };

function createParser(): StreamParser<QasmState> {
  return {
    name: "openqasm",
    startState: () => ({ isInBlockComment: false }),
    token: parseToken,
    languageData: { commentTokens: { line: "//", block: { open: "/*", close: "*/" } } },
    tokenTable: { function: tags.function(tags.variableName) },
  };
}

function parseToken(stream: StringStream, state: QasmState): string | null {
  if (state.isInBlockComment) {
    return parseBlockComment(stream, state);
  }
  if (stream.eatSpace()) {
    return null;
  }
  if (stream.match("//")) {
    stream.skipToEnd();
    return "lineComment";
  }
  if (stream.match("/*")) {
    state.isInBlockComment = true;
    return parseBlockComment(stream, state);
  }
  if (stream.match(/^"[^"]*"?/)) {
    return "string";
  }
  if (stream.match(NUMBER)) {
    return "number";
  }
  if (stream.match(PHYSICAL_QUBIT)) {
    return "atom";
  }
  const word = stream.match(IDENTIFIER);
  if (word && typeof word === "object") {
    return WORD_TYPES[word[0]] ?? "variableName";
  }
  if (stream.match(OPERATOR)) {
    return "operator";
  }
  stream.next();
  return null;
}

function parseBlockComment(stream: StringStream, state: QasmState): string {
  if (stream.skipTo("*/")) {
    stream.match("*/");
    state.isInBlockComment = false;
  } else {
    stream.skipToEnd();
  }
  return "blockComment";
}

function formatArity(parameters: number, qubits: number): string {
  const parameterText = parameters === 0 ? "" : `${parameters} param · `;
  return `${parameterText}${qubits} qubit${qubits === 1 ? "" : "s"}`;
}

function makeGhzCircuit(numberOfQubits: number): string {
  const size = Math.max(2, Math.min(numberOfQubits, 5));
  const entangling = Array.from(
    { length: size - 1 },
    (_, index) => `cx q[${index}], q[${index + 1}];`,
  ).join("\n");
  return `OPENQASM 3.0;\ninclude "stdgates.inc";\n\nqubit[${size}] q;\nbit[${size}] c;\n\nh q[0];\n${entangling}\nc = measure q;\n`;
}
