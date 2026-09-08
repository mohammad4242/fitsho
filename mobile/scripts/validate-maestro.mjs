import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export const REQUIRED_MAESTRO_FLOWS = [
  "launch.yaml",
  "member.yaml",
  "coach.yaml",
  "physician.yaml",
  "role-boundary.yaml",
];

const legacyBrandPattern = /Fitsho|Fitition/u;
const secretLiteralPattern = /(?:password|email|token)\s*:\s*[^$\s][^\n]*/iu;

export function validateMaestroFlows(files) {
  for (const required of REQUIRED_MAESTRO_FLOWS) {
    assert.equal(typeof files[required], "string", `missing Maestro flow ${required}`);
  }

  for (const [path, contents] of Object.entries(files)) {
    assert.equal(legacyBrandPattern.test(contents), false, `${path} contains a legacy brand`);
    assert.equal(secretLiteralPattern.test(contents), false, `${path} contains a literal secret`);
    if (path.startsWith("subflows/")) continue;
    assert.match(contents, /^appId:\s*com\.fitician\.app\s*$/mu, `${path} must use Fitician app id`);
    assert.match(contents, /^-\s+(?:clearState|launchApp)/mu, `${path} must launch from clean state`);
  }

  const launch = files["launch.yaml"];
  assert.match(launch, /assertVisible:\s*["']FITICIAN["']/u);
  for (const flowName of ["member.yaml", "coach.yaml", "physician.yaml", "role-boundary.yaml"]) {
    const flow = files[flowName];
    assert.match(flow, /subflows\/sign-in\.yaml/u, `${flowName} must reuse the sign-in flow`);
  }
  assert.match(files["member.yaml"], /تحلیل بدن/u);
  assert.match(files["coach.yaml"], /E2E: مربی/u);
  assert.match(files["physician.yaml"], /E2E: پزشک/u);
  assert.match(files["role-boundary.yaml"], /E2E: مربی/u);
  return files;
}

async function readYamlFiles(directory, prefix = "") {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = {};
  for (const entry of entries) {
    const relativePath = prefix ? `${prefix}/${entry.name}` : entry.name;
    const fullPath = resolve(directory, entry.name);
    if (entry.isDirectory()) {
      Object.assign(files, await readYamlFiles(fullPath, relativePath));
    } else if (entry.name.endsWith(".yaml")) {
      files[relativePath] = await readFile(fullPath, "utf8");
    }
  }
  return files;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const mobileRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
  const files = await readYamlFiles(resolve(mobileRoot, ".maestro"));
  validateMaestroFlows(files);
  console.log("Fitician Maestro flows are valid");
}
