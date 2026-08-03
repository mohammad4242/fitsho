import { cp, mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const projectDirectory = resolve(scriptDirectory, "..");
const sourceDirectory = resolve(
  projectDirectory,
  "node_modules/@mediapipe/tasks-vision/wasm",
);
const targetDirectory = resolve(projectDirectory, "public/mediapipe/wasm");

await mkdir(dirname(targetDirectory), { recursive: true });
await cp(sourceDirectory, targetDirectory, { recursive: true, force: true });
