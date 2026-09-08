import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const mobileRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const projectRoot = resolve(mobileRoot, "..");
const severities = ["info", "low", "moderate", "high", "critical"];

export function summarizeAudit(report) {
  const counts = Object.fromEntries(severities.map((severity) => [severity, 0]));
  for (const vulnerability of Object.values(report.vulnerabilities ?? {})) {
    if (vulnerability && typeof vulnerability.severity === "string" && vulnerability.severity in counts) {
      counts[vulnerability.severity] += 1;
    }
  }
  return { ...counts, total: Object.values(counts).reduce((sum, count) => sum + count, 0) };
}

export function assertAuditPolicy(report) {
  const counts = report.metadata?.vulnerabilities ?? summarizeAudit(report);
  if ((counts.high ?? 0) > 0 || (counts.critical ?? 0) > 0) {
    throw new Error(
      `Mobile dependency audit found high or critical advisories `
        + `(high=${counts.high ?? 0}, critical=${counts.critical ?? 0})`,
    );
  }
  return counts;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const result = spawnSync(
    "npm",
    ["audit", "--workspace=@fitician/mobile", "--omit=dev", "--json"],
    { cwd: projectRoot, encoding: "utf8" },
  );
  let report;
  try {
    report = JSON.parse(result.stdout);
  } catch {
    process.stderr.write(result.stderr || "npm audit did not return JSON\n");
    process.exit(1);
  }

  const counts = assertAuditPolicy(report);
  console.log(
    `Mobile dependency audit: ${counts.total} advisories `
      + `(moderate=${counts.moderate}, high=${counts.high}, critical=${counts.critical})`,
  );
}
