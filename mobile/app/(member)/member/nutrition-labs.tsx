import { NutritionClinicalSection } from "../../../nutrition/NutritionClinicalSection";
import { Screen } from "../../../ui/layout";
import { RouteGuard } from "../../../ui/navigation/RouteGuards";

export default function MemberNutritionLabsRoute() {
  return (
    <RouteGuard kind="member" requiredCapability="nutrition">
      <Screen contentWidth="reading">
        <NutritionClinicalSection mode="labs" />
      </Screen>
    </RouteGuard>
  );
}
