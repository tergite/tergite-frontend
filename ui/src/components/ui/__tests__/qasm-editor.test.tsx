import { render } from "@testing-library/react";
import { CompletionContext } from "@codemirror/autocomplete";
import { forEachDiagnostic } from "@codemirror/lint";
import { EditorState } from "@codemirror/state";
import { EditorView, runScopeHandlers } from "@codemirror/view";
import { describe, expect, it, vi } from "vitest";
import { QasmEditor } from "../qasm-editor";
import { BELL_CIRCUIT, makeQasmCompletions } from "@/lib/qasm/language";

describe("QasmEditor", () => {
  it("reports what is typed", () => {
    const onChange = vi.fn();
    const view = renderEditor({ value: "", onChange });

    view.dispatch({ changes: { from: 0, insert: "h q[0];" } });

    expect(onChange).toHaveBeenCalledWith("h q[0];");
  });

  it("shows a new value, as when a past run is loaded", () => {
    const { rerender, container } = render(
      <QasmEditor value="x q[0];" onChange={() => {}} />,
    );

    rerender(<QasmEditor value={BELL_CIRCUIT} onChange={() => {}} />);

    expect(findView(container).state.doc.toString()).toBe(BELL_CIRCUIT);
  });

  it("runs on Mod-Enter", () => {
    const onRun = vi.fn();
    const view = renderEditor({ value: BELL_CIRCUIT, onRun });

    // Mod is Cmd on a Mac and Ctrl elsewhere, as CodeMirror reads the platform
    const isMac = /Mac|iPhone|iPad/.test(navigator.platform);
    const isHandled = runScopeHandlers(
      view,
      new KeyboardEvent("keydown", { key: "Enter", ctrlKey: !isMac, metaKey: isMac }),
      "editor",
    );

    expect(isHandled).toBe(true);
    expect(onRun).toHaveBeenCalledOnce();
  });

  it("marks an error from its line and column to the end of the line", () => {
    const view = renderEditor({
      value: BELL_CIRCUIT,
      errors: [{ message: "missing ';' at 'cx'", line: 7, column: 3 }],
    });

    const found: { from: number; to: number; message: string }[] = [];
    forEachDiagnostic(view.state, (diagnostic, from, to) =>
      found.push({ from, to, message: diagnostic.message }),
    );

    const line = view.state.doc.line(7);
    expect(found).toEqual([
      { from: line.from + 2, to: line.to, message: "missing ';' at 'cx'" },
    ]);
  });
});

describe("makeQasmCompletions", () => {
  it("offers gates with their arity, the device's frames and its qubits", () => {
    const source = makeQasmCompletions(5, ["q12_drive"]);
    const state = EditorState.create({ doc: "c" });

    const result = source(new CompletionContext(state, 1, true));

    const labels = Object.fromEntries(
      (result?.options ?? []).map((option) => [option.label, option.detail]),
    );
    expect(labels["cx"]).toBe("2 qubits");
    expect(labels["rx"]).toBe("1 param · 1 qubit");
    expect(labels["q12_drive"]).toBe("frame");
    expect(labels["qubit[5]"]).toBe("all qubits");
  });

  it("offers nothing unasked before a word is started", () => {
    const source = makeQasmCompletions(5, []);
    const state = EditorState.create({ doc: "h q[0]; " });

    expect(source(new CompletionContext(state, 8, false))).toBeNull();
  });
});

function renderEditor(props: Partial<Parameters<typeof QasmEditor>[0]>) {
  const { container } = render(
    <QasmEditor value="" onChange={() => {}} {...props} />,
  );
  return findView(container);
}

function findView(container: HTMLElement): EditorView {
  const editor = container.querySelector<HTMLElement>(".cm-editor");
  return EditorView.findFromDOM(editor!)!;
}
