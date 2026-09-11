import { spawnSync } from "node:child_process";
import { readFileSync, statSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const mobileRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const projectRoot = resolve(mobileRoot, "..");

const highConfidencePatterns = [
  { rule: "private-key", pattern: /-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----/u },
  { rule: "aws-access-key", pattern: /\b(?:AKIA|ASIA)[A-Z0-9]{16}\b/u },
  { rule: "google-api-key", pattern: /\bAIza[A-Za-z0-9_-]{35}\b/u },
  { rule: "openai-compatible-key", pattern: /\bsk-[A-Za-z0-9_-]{20,}\b/u },
  { rule: "github-token", pattern: /\b(?:gh[pousr]|github_pat)_[A-Za-z0-9_]{20,}\b/u },
  { rule: "slack-token", pattern: /\bxox[baprs]-[A-Za-z0-9-]{20,}\b/u },
  { rule: "jwt", pattern: /\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b/u },
];

const quotedSecretPattern = /\b(?:api[_-]?key|client[_-]?secret|service[_-]?secret|access[_-]?token|refresh[_-]?token|auth[_-]?token|password|private[_-]?key)\b\s*[:=]\s*["'`]([^"'`\r\n]{16,})["'`]/giu;

const placeholderPattern = /(?:^|\b)(?:your|replace|example|sample|dummy|fake|test|secret|token|password|redacted|placeholder|changeme|configure|api[-_]?key|access[-_]?token|refresh[-_]?token|correct horse battery staple|long password|(?:access|refresh|refreshed|rotated|initial|soon[-_]?expired|fresh|stale)(?:[-_]|$)|<[^>]+>)(?:$|\b)/iu;

function isPlaceholder(value) {
  return value.trim().length === 0 || placeholderPattern.test(value.trim());
}

export function findSecretMatches(source) {
  const matches = [];
  const seen = new Set();
  const lines = source.split(/\r?\n/u);

  const addMatch = (line, rule) => {
    const key = `${line}:${rule}`;
    if (!seen.has(key)) {
      seen.add(key);
      matches.push({ line, rule });
    }
  };

  lines.forEach((lineText, index) => {
    const line = index + 1;
    for (const { rule, pattern } of highConfidencePatterns) {
      if (pattern.test(lineText)) addMatch(line, rule);
      pattern.lastIndex = 0;
    }

    quotedSecretPattern.lastIndex = 0;
    for (const match of lineText.matchAll(quotedSecretPattern)) {
      if (!isPlaceholder(match[1])) addMatch(line, "quoted-secret");
    }
  });

  return matches;
}

export function scanTrackedFiles(root = projectRoot) {
  const result = spawnSync("git", ["ls-files", "-z"], {
    cwd: root,
    encoding: "utf8",
  });
  if (result.status !== 0) {
    throw new Error(result.stderr || "Unable to list tracked files");
  }

  const findings = [];
  for (const relativePath of result.stdout.split("\0")) {
    if (!relativePath) continue;
    const filePath = resolve(root, relativePath);
    const fileStats = statSync(filePath, { throwIfNoEntry: false });
    if (fileStats === undefined || !fileStats.isFile()) continue;
    const source = readFileSync(filePath);
    if (source.includes(0)) continue;

    for (const finding of findSecretMatches(source.toString("utf8"))) {
      findings.push({ path: relativePath, ...finding });
    }
  }
  return findings;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const findings = scanTrackedFiles();
  if (findings.length > 0) {
    for (const finding of findings) {
      console.error(`${finding.path}:${finding.line}: ${finding.rule}`);
    }
    process.exitCode = 1;
  } else {
    console.log("Tracked secret scan passed");
  }
}
