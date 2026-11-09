import { readFileSync } from "fs";
import path from "path";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Node 25 onwards has a localStorage of its own, which shadows happy-dom's in the tests, and
// is unusable without a file; Node before 22.4 has no such flag, and refuses one it lacks
const testExecArgv = process.allowedNodeEnvironmentFlags.has(
  "--experimental-webstorage",
)
  ? ["--no-experimental-webstorage"]
  : [];
const { version } = JSON.parse(
  readFileSync(path.resolve(__dirname, "package.json"), "utf-8"),
);

// https://vitejs.dev/config/
export default defineConfig({
  // where MSS serves it, as the dashboard's pages are API paths too; dev and test runs share it
  base: "/ui/",
  plugins: [react()],
  // the release the top bar announces, fixed at build time
  define: { "import.meta.env.VITE_APP_VERSION": JSON.stringify(version) },
  test: {
    globals: true,
    include: ["src/**/__tests__/*"],
    environment: "happy-dom",
    setupFiles: "src/setupTests.ts",
    poolOptions: {
      forks: { execArgv: testExecArgv },
      threads: { execArgv: testExecArgv },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    cors: {
      credentials: true,
      origin: true,
      methods: ["GET", "PUT", "POST", "DELETE", "PATCH", "HEAD"],
    },
  },
});
