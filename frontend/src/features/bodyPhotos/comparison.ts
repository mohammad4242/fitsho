import type {
  BodyAnalysisClassification,
  BodyArea,
  BodyAreaComparison,
  NormalizedBodyAnalysis,
} from "./types";

const minimumComparisonConfidence = 0.6;

const classificationRank: Record<BodyAnalysisClassification, number | null> = {
  clear_lag: 0,
  mild_lag: 1,
  neutral: 2,
  strength: 3,
  uncertain: null,
};

export function compareNormalizedAnalyses(
  previous: NormalizedBodyAnalysis,
  current: NormalizedBodyAnalysis,
): BodyAreaComparison[] {
  const previousByArea = new Map(previous.findings.map((finding) => [finding.body_area, finding]));
  const currentByArea = new Map(current.findings.map((finding) => [finding.body_area, finding]));
  const areas = new Set<BodyArea>([...previousByArea.keys(), ...currentByArea.keys()]);

  return [...areas].map((bodyArea) => {
    const previousFinding = previousByArea.get(bodyArea);
    const currentFinding = currentByArea.get(bodyArea);
    const confidence = Math.min(
      previous.overall_confidence,
      current.overall_confidence,
      previousFinding?.confidence ?? 0,
      currentFinding?.confidence ?? 0,
    );
    const previousRank = previousFinding === undefined
      ? null
      : classificationRank[previousFinding.classification];
    const currentRank = currentFinding === undefined
      ? null
      : classificationRank[currentFinding.classification];

    let state: BodyAreaComparison["state"] = "uncertain";
    if (
      confidence >= minimumComparisonConfidence
      && previousRank !== null
      && currentRank !== null
    ) {
      state = currentRank > previousRank
        ? "improved"
        : currentRank < previousRank
          ? "declined_or_less_balanced"
          : "unchanged";
    }

    return {
      bodyArea,
      state,
      previousClassification: previousFinding?.classification ?? null,
      currentClassification: currentFinding?.classification ?? null,
      confidence,
    };
  });
}
