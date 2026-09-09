import { BodyAnalysisHistoryScreen } from "../../../../bodyAnalysis/BodyAnalysisHistoryScreen";
import { RouteGuard } from "../../../../ui/navigation/RouteGuards";

export default function MemberBodyAnalysisTabScreen() {
  return (
    <RouteGuard kind="member" requiredCapability="training">
      <BodyAnalysisHistoryScreen tabRoot />
    </RouteGuard>
  );
}
