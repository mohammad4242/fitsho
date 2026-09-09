import { NutritionTrackingSection } from "../../../nutrition/NutritionTrackingSection";
import { Screen } from "../../../ui/layout";
import { RouteGuard } from "../../../ui/navigation/RouteGuards";

export default function MemberNutritionTrackingRoute() {
  return (
    <RouteGuard kind="member" requiredCapability="nutrition">
      <Screen contentWidth="reading">
        <NutritionTrackingSection />
      </Screen>
    </RouteGuard>
  );
}
