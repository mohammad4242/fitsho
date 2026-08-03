import { expect, it } from "vitest";

import { compareNormalizedAnalyses, deriveOverallProgressState } from "./comparison";
import type { NormalizedBodyAnalysis } from "./types";

function normalized(
  classification: "strength" | "mild_lag" | "clear_lag" | "uncertain",
  confidence = 0.9,
): NormalizedBodyAnalysis {
  return {
    schema_version: "1.0",
    overall_confidence: confidence,
    findings: [{
      body_area: "shoulders",
      classification,
      severity: classification === "mild_lag" ? 0.45 : classification === "clear_lag" ? 0.8 : null,
      confidence,
      supporting_views: ["front", "back"],
      explanation: "Visible shoulder proportion.",
      limitations: [],
      suggested_training_emphasis: classification === "uncertain" ? [] : ["lateral_deltoid"],
      medical_review_recommended: false,
    }],
    summary: {
      visible_strengths: classification === "strength" ? ["shoulders"] : [],
      priority_areas: classification === "clear_lag" ? ["shoulders"] : [],
      moderate_attention_areas: classification === "mild_lag" ? ["shoulders"] : [],
      uncertain_areas: classification === "uncertain" ? ["shoulders"] : [],
    },
    requires_coach_review: true,
    requires_doctor_review: true,
  };
}

it("reports a conservative improvement from clear lag to mild lag", () => {
  expect(compareNormalizedAnalyses(normalized("clear_lag"), normalized("mild_lag"))).toEqual([
    expect.objectContaining({ bodyArea: "shoulders", state: "improved" }),
  ]);
});

it("returns uncertain when either session has low confidence or uncertain evidence", () => {
  expect(compareNormalizedAnalyses(normalized("clear_lag", 0.4), normalized("mild_lag"))[0]?.state).toBe("uncertain");
  expect(compareNormalizedAnalyses(normalized("uncertain"), normalized("mild_lag"))[0]?.state).toBe("uncertain");
});

it("derives a single overall progress state from confident area comparisons", () => {
  expect(deriveOverallProgressState([
    {
      bodyArea: "shoulders",
      state: "improved",
      previousClassification: "mild_lag",
      currentClassification: "neutral",
      confidence: 0.8,
    },
    {
      bodyArea: "chest",
      state: "unchanged",
      previousClassification: "neutral",
      currentClassification: "neutral",
      confidence: 0.8,
    },
  ])).toBe("improved");
  expect(deriveOverallProgressState([
    {
      bodyArea: "shoulders",
      state: "uncertain",
      previousClassification: null,
      currentClassification: null,
      confidence: 0.2,
    },
  ])).toBe("insufficient_data");
});
