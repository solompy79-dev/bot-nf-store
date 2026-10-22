import { spawn } from "node:child_process";
const child = spawn(process.execPath, ["node_modules/vite/bin/vite.js", "dev", "--host", "127.0.0.1", "--port", "5173", "--strictPort"], {
  stdio: "inherit",
  env: { ...process.env, LOCAL_AUTH: "true", VITE_LOCAL_AUTH: "true", LOVABLE_API_KEY: process.env.LOVABLE_API_KEY || "local-preview-placeholder" },
});
for (const event of ["SIGINT", "SIGTERM"]) process.on(event, () => child.kill(event));
child.on("exit", code => process.exit(code ?? 1));
