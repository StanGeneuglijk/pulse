import path from "node:path";
import { defineConfig } from "vitest/config";

// Unit tests for pure modules and route handlers: no DOM needed.
export default defineConfig({
  // Next compiles JSX with the automatic runtime (no `import React`); match it.
  esbuild: { jsx: "automatic" },
  resolve: {
    alias: { "@": path.resolve(__dirname) },
  },
  test: {
    environment: "node",
    include: ["tests/**/*.test.ts"],
  },
});
