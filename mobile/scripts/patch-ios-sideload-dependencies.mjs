import { readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const INVALID_RUNTIME_SCHEDULER_ANNOTATION = /SWIFT_RETURNS_RETAINED(?=\s+RuntimeScheduler\s*\()/gu;

export function stripInvalidRuntimeSchedulerOwnershipAnnotations(source) {
  const annotations = source.match(INVALID_RUNTIME_SCHEDULER_ANNOTATION) ?? [];
  if (annotations.length !== 0 && annotations.length !== 2) {
    throw new Error(
      `Expected two RuntimeScheduler constructor annotations, found ${annotations.length}`,
    );
  }
  return source.replace(INVALID_RUNTIME_SCHEDULER_ANNOTATION, "");
}

if (import.meta.url === `file://${process.argv[1]}`) {
  if (process.env.IOS_SIDELOAD_BUILD !== "1") {
    throw new Error("IOS_SIDELOAD_BUILD=1 is required for the iOS sideload dependency patch");
  }

  const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
  const headerPath = resolve(
    projectRoot,
    "node_modules/expo-modules-jsi/apple/Sources/ExpoModulesJSI-Cxx/include/RuntimeScheduler.h",
  );
  const source = await readFile(headerPath, "utf8");
  const patched = stripInvalidRuntimeSchedulerOwnershipAnnotations(source);
  if (patched !== source) {
    await writeFile(headerPath, patched);
    console.log(`Patched ${headerPath} for Swift 6.2 C++ interop`);
  } else {
    console.log(`No RuntimeScheduler ownership patch needed in ${headerPath}`);
  }
}
