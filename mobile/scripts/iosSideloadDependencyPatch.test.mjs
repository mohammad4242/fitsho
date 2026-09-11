import assert from "node:assert/strict";
import test from "node:test";

import {
  stripInvalidRuntimeSchedulerOwnershipAnnotations,
} from "./patch-ios-sideload-dependencies.mjs";

const runtimeSchedulerHeader = `
class RuntimeScheduler {
  SWIFT_RETURNS_RETAINED RuntimeScheduler(void *scheduler, ScheduleFn fn) noexcept {}
  SWIFT_RETURNS_RETAINED RuntimeScheduler() {}
} SWIFT_SHARED_REFERENCE(retainRuntimeScheduler, releaseRuntimeScheduler);
`;

test("sideload dependency patch removes only invalid RuntimeScheduler constructor annotations", () => {
  const patched = stripInvalidRuntimeSchedulerOwnershipAnnotations(runtimeSchedulerHeader);
  assert.equal(patched.match(/SWIFT_RETURNS_RETAINED/gu), null);
  assert.match(patched, /RuntimeScheduler\(void \*scheduler, ScheduleFn fn\)/u);
  assert.match(patched, /RuntimeScheduler\(\) \{\}/u);
  assert.match(patched, /SWIFT_SHARED_REFERENCE\(retainRuntimeScheduler, releaseRuntimeScheduler\)/u);
});

test("sideload dependency patch is idempotent", () => {
  const once = stripInvalidRuntimeSchedulerOwnershipAnnotations(runtimeSchedulerHeader);
  assert.equal(stripInvalidRuntimeSchedulerOwnershipAnnotations(once), once);
});
