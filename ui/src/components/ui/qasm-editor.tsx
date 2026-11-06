import { useEffect, useRef } from "react";
import { autocompletion } from "@codemirror/autocomplete";
import { syntaxHighlighting } from "@codemirror/language";
import { type Diagnostic, lintGutter, setDiagnostics } from "@codemirror/lint";
import { Compartment, EditorState, Prec, type Text } from "@codemirror/state";
import { EditorView, keymap } from "@codemirror/view";
import { basicSetup } from "codemirror";
import {
  QASM_HIGHLIGHT,
  QASM_LANGUAGE,
  makeQasmCompletions,
} from "@/lib/qasm/language";
import { cn } from "@/lib/utils";

// shared, so that an editor given none keeps the same array between renders
const NO_FRAMES: string[] = [];
const NO_ERRORS: QasmError[] = [];

/**
 * An OpenQASM 3 editor: highlighting, completion for the device, and errors at their line.
 *
 * The view is built once; props reach it through refs, and what changes with the device sits
 * in a Compartment, so the cursor and undo history survive. Mod-Enter runs the circuit.
 */
export function QasmEditor({
  value,
  onChange,
  onRun,
  numberOfQubits = 0,
  frames = NO_FRAMES,
  errors = NO_ERRORS,
  label = "Circuit",
  className,
}: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef<EditorView | null>(null);
  const completionRef = useRef(new Compartment());
  const onChangeRef = useRef(onChange);
  const onRunRef = useRef(onRun);
  onChangeRef.current = onChange;
  onRunRef.current = onRun;

  useEffect(() => {
    const view = new EditorView({
      parent: hostRef.current!,
      state: EditorState.create({
        doc: value,
        extensions: [
          Prec.highest(
            keymap.of([
              {
                key: "Mod-Enter",
                run: () => {
                  onRunRef.current?.();
                  return true;
                },
              },
            ]),
          ),
          basicSetup,
          QASM_LANGUAGE,
          syntaxHighlighting(QASM_HIGHLIGHT),
          completionRef.current.of(
            autocompletion({ override: [makeQasmCompletions(numberOfQubits, frames)] }),
          ),
          lintGutter(),
          EditorView.contentAttributes.of({ "aria-label": label }),
          EditorView.updateListener.of((update) => {
            if (update.docChanged) {
              onChangeRef.current(update.state.doc.toString());
            }
          }),
        ],
      }),
    });
    viewRef.current = view;
    return () => {
      view.destroy();
      viewRef.current = null;
    };
    // built once: later props reach the view through refs and the effects below
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const view = viewRef.current;
    if (view && view.state.doc.toString() !== value) {
      view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: value } });
    }
  }, [value]);

  useEffect(() => {
    viewRef.current?.dispatch({
      effects: completionRef.current.reconfigure(
        autocompletion({ override: [makeQasmCompletions(numberOfQubits, frames)] }),
      ),
    });
  }, [numberOfQubits, frames]);

  useEffect(() => {
    const view = viewRef.current;
    if (view) {
      const diagnostics = errors.map((error) => convertToDiagnostic(view.state.doc, error));
      view.dispatch(setDiagnostics(view.state, diagnostics));
    }
  }, [errors]);

  return (
    <div
      ref={hostRef}
      className={cn("qasm-editor min-h-0 overflow-hidden", className)}
      data-cy-qasm-editor
    />
  );
}

/** A problem in the circuit, from 1 like an editor counts lines and columns */
export interface QasmError {
  message: string;
  line?: number | null;
  column?: number | null;
}

function convertToDiagnostic(doc: Text, error: QasmError): Diagnostic {
  if (!error.line) {
    return { from: 0, to: 0, severity: "error", message: error.message };
  }
  const line = doc.line(Math.min(Math.max(error.line, 1), doc.lines));
  const from = Math.min(line.from + Math.max((error.column ?? 1) - 1, 0), line.to);
  return { from, to: line.to, severity: "error", message: error.message };
}

interface Props {
  value: string;
  onChange: (value: string) => void;
  onRun?: () => void;
  numberOfQubits?: number;
  frames?: string[];
  errors?: QasmError[];
  label?: string;
  className?: string;
}
