import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // Resolução nativa dos caminhos do tsconfig (`@/…`) — dispensa o plugin.
  resolve: { tsconfigPaths: true },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/preparo.ts"],
    include: ["tests/**/*.teste.{ts,tsx}"],
    css: false,
  },
});
