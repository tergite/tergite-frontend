// @vitest-environment node
/**
 * The house style that eslint and tsc cannot enforce, checked on every test run.
 *
 * Code that broke a rule when the rule was added is listed in
 * fixtures/styleguide-baseline.txt. That list may only shrink: a new violation fails, and
 * so does a listed one that has been fixed but not deleted from the list.
 */
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, normalize, relative } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";
import { describe, expect, it } from "vitest";

const APP_ROOT = fileURLToPath(new URL("../../", import.meta.url));
const BASELINE_FILE = join(
  APP_ROOT,
  "src/__tests__/fixtures/styleguide-baseline.txt",
);
const CODE_ROOTS = ["src", "api", "types.ts"];
const SKIPPED_DIRS = new Set(["__tests__", "node_modules"]);
// a new verb is added here in review, never to the baseline
const VERBS = new Set([
  "accept", "add", "apply", "authenticate", "build", "calculate", "cancel",
  "check", "choose", "clear", "close", "collect", "compare", "compute",
  "confirm", "connect", "convert", "copy", "count", "create", "decode",
  "delete", "derive", "dismiss", "edit", "emit", "encode", "ensure", "extend",
  "extract", "fetch", "filter", "find", "format", "forward", "generate",
  "get", "group", "handle", "hide", "init", "insert", "is", "load", "log",
  "login", "logout", "make", "map", "mark", "merge", "move", "navigate",
  "normalize", "notify", "open", "order", "parse", "pick", "prepare",
  "refresh", "remove", "render", "replace", "request", "require", "reset",
  "resolve", "respond", "run", "save", "search", "select", "send",
  "serialize", "set", "should", "show", "sort", "split", "start", "stop",
  "submit", "switch", "toggle", "transform", "try", "update", "upload",
  "use", "validate", "verify", "view", "wait", "write",
]);
const HOOK_PREFIX = "on";
const BOOLEAN_NAME = /^_?(is|should)[A-Z0-9_]/;
const PASCAL_CASE = /^[A-Z][A-Za-z0-9]*$/;
const CONSTANT_NAME = /^_?[A-Z][A-Z0-9_]*$/;
const BANNER_COMMENT =
  /^(?:\/\/|\/\*+)\s*(?:[-=*#~_]{10,}|[-=*#~_]{3,}\s*\S.*\S\s*[-=*#~_]{3,})\s*(?:\*\/)?$/;
const FETCH_HOMES = new Set(["src/lib/api-client.ts", "src/lib/api/client.ts"]);
const UI_DIR = "src/components/ui/";
const PAGES_DIR = "src/pages/";
const MOCK_API_DIRS = ["api/", "dev/mock-api/"];

type Violation = { rule: string; location: string };
type Module = { name: string; source: ts.SourceFile };
type Rule = { check: (module: Module) => Violation[]; roots: string[] };

describe("styleguide", () => {
  it.each(Object.keys(getRules()))("%s has no new violations", (rule) => {
    const baseline = readBaseline();
    const fresh = findViolations(rule)
      .map(formatViolation)
      .filter((violation) => !baseline.has(violation));

    expect(fresh.join("\n")).toBe("");
  });

  it("baseline lists only current violations", () => {
    const current = new Set(
      Object.keys(getRules()).flatMap((rule) =>
        findViolations(rule).map(formatViolation),
      ),
    );
    const fixed = [...readBaseline()].filter((entry) => !current.has(entry));

    expect(fixed.join("\n")).toBe("");
  });

  it("catches what each rule describes", () => {
    const sample = parseModule(
      "src/components/ui/sample.tsx",
      [
        'import { thing } from "@/pages/home/components/thing";',
        "function helper(): void {}",
        "export function jobStatus(active: boolean): void { fetch(thing); }",
        "// ---- jobs ----",
        "const LIMIT = 5;",
      ].join("\n"),
    );

    const found = Object.values(getRules()).flatMap(({ check }) =>
      check(sample).map(formatViolation),
    );

    expect(new Set(found)).toEqual(
      new Set([
        "verb: src/components/ui/sample.tsx::helper",
        "verb: src/components/ui/sample.tsx::jobStatus",
        "boolean: src/components/ui/sample.tsx::active",
        "private-helper-position: src/components/ui/sample.tsx::jobStatus",
        "constant-position: src/components/ui/sample.tsx::LIMIT",
        "banner: src/components/ui/sample.tsx:4",
        "import-layering: src/components/ui/sample.tsx::import @/pages/home/components/thing",
        "fetch-home: src/components/ui/sample.tsx",
      ]),
    );
  });
});

function getRules(): Record<string, Rule> {
  return {
    verb: { check: checkVerbs, roots: CODE_ROOTS },
    boolean: { check: checkBooleans, roots: CODE_ROOTS },
    "constant-position": { check: checkConstantPositions, roots: CODE_ROOTS },
    "private-helper-position": {
      check: checkPrivateHelperPositions,
      roots: CODE_ROOTS,
    },
    "props-position": { check: checkPropsPositions, roots: ["src"] },
    banner: { check: checkBanners, roots: CODE_ROOTS },
    "import-layering": { check: checkImportLayering, roots: ["src"] },
    "fetch-home": { check: checkFetchHome, roots: ["src"] },
  };
}

function findViolations(rule: string): Violation[] {
  const { check, roots } = getRules()[rule];
  return readModules(roots).flatMap(check);
}

function formatViolation({ rule, location }: Violation): string {
  return `${rule}: ${location}`;
}

function readBaseline(): Set<string> {
  if (!existsSync(BASELINE_FILE)) return new Set();
  return new Set(
    readFileSync(BASELINE_FILE, "utf-8")
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line && !line.startsWith("#")),
  );
}

function readModules(roots: string[]): Module[] {
  return roots
    .flatMap((root) => listSourceFiles(join(APP_ROOT, root)))
    .map((path) =>
      parseModule(relative(APP_ROOT, path), readFileSync(path, "utf-8")),
    );
}

function listSourceFiles(path: string): string[] {
  if (!existsSync(path)) return [];
  if (statSync(path).isFile()) return [path];
  return readdirSync(path)
    .filter((entry) => !SKIPPED_DIRS.has(entry))
    .flatMap((entry) => listSourceFiles(join(path, entry)))
    .filter((file) => /\.tsx?$/.test(file) && !file.endsWith(".d.ts"))
    .sort();
}

function parseModule(name: string, text: string): Module {
  const kind = name.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
  return {
    name,
    source: ts.createSourceFile(name, text, ts.ScriptTarget.Latest, true, kind),
  };
}

function checkVerbs(module: Module): Violation[] {
  return findFunctions(module.source)
    .filter(({ name }) => !PASCAL_CASE.test(name) && !startsWithVerb(name))
    .map(({ name }) => ({ rule: "verb", location: `${module.name}::${name}` }));
}

function checkBooleans(module: Module): Violation[] {
  const violations: Violation[] = [];
  visitNodes(module.source, (node) => {
    const isNamedDeclaration =
      ts.isParameter(node) ||
      ts.isVariableDeclaration(node) ||
      ts.isPropertySignature(node) ||
      ts.isPropertyDeclaration(node);
    if (!isNamedDeclaration || !node.type || !isBooleanType(node.type)) return;
    const name = node.name.getText(module.source);
    if (!BOOLEAN_NAME.test(name)) {
      violations.push({ rule: "boolean", location: `${module.name}::${name}` });
    }
  });
  return violations;
}

function checkConstantPositions(module: Module): Violation[] {
  const definedNames = new Set<string>();
  const violations: Violation[] = [];
  for (const statement of module.source.statements) {
    const functionNames = getTopLevelFunctionNames(statement);
    if (functionNames.length > 0) {
      functionNames.forEach((name) => definedNames.add(name));
      continue;
    }
    if (!ts.isVariableStatement(statement) || definedNames.size === 0) continue;
    const isBuiltFromDefinitions = getIdentifiers(statement).some((name) =>
      definedNames.has(name),
    );
    for (const declaration of statement.declarationList.declarations) {
      const name = declaration.name.getText(module.source);
      if (CONSTANT_NAME.test(name) && !isBuiltFromDefinitions) {
        violations.push({
          rule: "constant-position",
          location: `${module.name}::${name}`,
        });
      }
    }
  }
  return violations;
}

function checkPrivateHelperPositions(module: Module): Violation[] {
  const violations: Violation[] = [];
  let hasPrivateFunctionAbove = false;
  for (const statement of module.source.statements) {
    const functionNames = getTopLevelFunctionNames(statement);
    if (functionNames.length === 0) continue;
    if (!isExported(statement)) {
      hasPrivateFunctionAbove = true;
    } else if (hasPrivateFunctionAbove) {
      functionNames.forEach((name) =>
        violations.push({
          rule: "private-helper-position",
          location: `${module.name}::${name}`,
        }),
      );
    }
  }
  return violations;
}

function checkPropsPositions(module: Module): Violation[] {
  const statements = module.source.statements;
  const firstFunctionIndex = statements.findIndex(
    (statement) => getTopLevelFunctionNames(statement).length > 0,
  );
  const propsIndex = statements.findIndex(
    (statement) =>
      (ts.isInterfaceDeclaration(statement) ||
        ts.isTypeAliasDeclaration(statement)) &&
      statement.name.text === "Props",
  );
  const isPropsAboveComponent =
    propsIndex !== -1 &&
    firstFunctionIndex !== -1 &&
    propsIndex < firstFunctionIndex;
  return isPropsAboveComponent
    ? [{ rule: "props-position", location: `${module.name}::Props` }]
    : [];
}

function checkBanners(module: Module): Violation[] {
  return module.source.text
    .split("\n")
    .map((line, index) => ({ line: line.trim(), lineNumber: index + 1 }))
    .filter(({ line }) => BANNER_COMMENT.test(line))
    .map(({ lineNumber }) => ({
      rule: "banner",
      location: `${module.name}:${lineNumber}`,
    }));
}

function checkImportLayering(module: Module): Violation[] {
  return module.source.statements
    .filter(ts.isImportDeclaration)
    .map((statement) => (statement.moduleSpecifier as ts.StringLiteral).text)
    .filter((specifier) => isForbiddenImport(module.name, specifier))
    .map((specifier) => ({
      rule: "import-layering",
      location: `${module.name}::import ${specifier}`,
    }));
}

function checkFetchHome(module: Module): Violation[] {
  if (FETCH_HOMES.has(module.name)) return [];
  let isFetchCalled = false;
  visitNodes(module.source, (node) => {
    if (
      ts.isCallExpression(node) &&
      ts.isIdentifier(node.expression) &&
      node.expression.text === "fetch"
    ) {
      isFetchCalled = true;
    }
  });
  return isFetchCalled ? [{ rule: "fetch-home", location: module.name }] : [];
}

function isForbiddenImport(importer: string, specifier: string): boolean {
  const target = resolveSpecifier(importer, specifier);
  if (target === undefined) return false;
  const isMockApi = MOCK_API_DIRS.some((dir) => target.startsWith(dir));
  const isPageFromUi =
    importer.startsWith(UI_DIR) && target.startsWith(PAGES_DIR);
  return isMockApi || isPageFromUi || isAnotherPage(importer, target);
}

function isAnotherPage(importer: string, target: string): boolean {
  const importerPage = getPageName(importer);
  const targetPage = getPageName(target);
  return (
    importerPage !== undefined &&
    targetPage !== undefined &&
    importerPage !== targetPage &&
    target.includes("/components/")
  );
}

function getPageName(path: string): string | undefined {
  if (!path.startsWith(PAGES_DIR)) return undefined;
  return path.slice(PAGES_DIR.length).split("/")[0].replace(/\.tsx?$/, "");
}

function resolveSpecifier(
  importer: string,
  specifier: string,
): string | undefined {
  if (specifier.startsWith("@/")) return `src/${specifier.slice(2)}`;
  if (!specifier.startsWith(".")) return undefined;
  return normalize(join(dirname(importer), specifier)).split("\\").join("/");
}

function findFunctions(source: ts.SourceFile): { name: string }[] {
  const functions: { name: string }[] = [];
  visitNodes(source, (node) => {
    if (ts.isFunctionDeclaration(node) && node.name) {
      functions.push({ name: node.name.text });
    } else if (ts.isMethodDeclaration(node) && ts.isIdentifier(node.name)) {
      functions.push({ name: node.name.text });
    } else if (
      ts.isVariableDeclaration(node) &&
      ts.isIdentifier(node.name) &&
      node.initializer &&
      (ts.isArrowFunction(node.initializer) ||
        ts.isFunctionExpression(node.initializer))
    ) {
      functions.push({ name: node.name.text });
    }
  });
  return functions;
}

function getTopLevelFunctionNames(statement: ts.Statement): string[] {
  if (ts.isFunctionDeclaration(statement) && statement.name) {
    return [statement.name.text];
  }
  if (!ts.isVariableStatement(statement)) return [];
  return statement.declarationList.declarations
    .filter(
      (declaration) =>
        declaration.initializer &&
        (ts.isArrowFunction(declaration.initializer) ||
          ts.isFunctionExpression(declaration.initializer)),
    )
    .map((declaration) => declaration.name.getText());
}

function getIdentifiers(node: ts.Node): string[] {
  const names: string[] = [];
  visitNodes(node, (child) => {
    if (ts.isIdentifier(child)) names.push(child.text);
  });
  return names;
}

function visitNodes(node: ts.Node, visit: (node: ts.Node) => void): void {
  visit(node);
  ts.forEachChild(node, (child) => visitNodes(child, visit));
}

function isExported(statement: ts.Statement): boolean {
  return (
    ts.canHaveModifiers(statement) &&
    (ts.getModifiers(statement) ?? []).some(
      (modifier) => modifier.kind === ts.SyntaxKind.ExportKeyword,
    )
  );
}

function isBooleanType(type: ts.TypeNode): boolean {
  if (type.kind === ts.SyntaxKind.BooleanKeyword) return true;
  return (
    ts.isUnionTypeNode(type) &&
    type.types.some((member) => member.kind === ts.SyntaxKind.BooleanKeyword) &&
    type.types.every(
      (member) =>
        member.kind === ts.SyntaxKind.BooleanKeyword ||
        member.kind === ts.SyntaxKind.UndefinedKeyword ||
        (ts.isLiteralTypeNode(member) &&
          member.literal.kind === ts.SyntaxKind.NullKeyword),
    )
  );
}

function startsWithVerb(name: string): boolean {
  const firstWord = name.replace(/^_+/, "").split(/(?=[A-Z0-9])/)[0];
  return VERBS.has(firstWord) || firstWord === HOOK_PREFIX;
}
