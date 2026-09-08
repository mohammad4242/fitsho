import assert from "node:assert/strict";
import test from "node:test";

import { assertAuditPolicy, summarizeAudit } from "./dependency-audit.mjs";

test("summarizes npm audit severity counts", () => {
  assert.deepEqual(
    summarizeAudit({
      vulnerabilities: {
        expo: { severity: "moderate" },
        uuid: { severity: "moderate" },
        example: { severity: "low" },
      },
    }),
    { info: 0, low: 1, moderate: 2, high: 0, critical: 0, total: 3 },
  );
});

test("rejects high and critical advisories while allowing reviewed lower severities", () => {
  assert.doesNotThrow(() => assertAuditPolicy({
    metadata: { vulnerabilities: { low: 0, moderate: 2, high: 0, critical: 0 } },
  }));
  assert.throws(
    () => assertAuditPolicy({
      metadata: { vulnerabilities: { low: 0, moderate: 0, high: 1, critical: 0 } },
    }),
    /high or critical/,
  );
});
