import { useLocalSearchParams, useRouter } from "expo-router";

import { BodyAnalysisWizard } from "../../../bodyAnalysis/BodyAnalysisWizard";
import { bodyPhotoPurposeFromParam } from "../../../bodyAnalysis/bodyPhotoWizardModel";

export default function MemberBodyAnalysisCaptureScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ purpose?: string | string[]; sessionId?: string | string[] }>();
  const sessionId = firstParam(params.sessionId);
  const purpose = bodyPhotoPurposeFromParam(firstParam(params.purpose));

  return (
    <BodyAnalysisWizard
      onExit={() => router.replace("/member")}
      onViewAnalysis={(id) => router.push(`/member/body-analysis-result/${encodeURIComponent(id)}`)}
      purpose={purpose}
      sessionId={sessionId}
    />
  );
}

function firstParam(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}
