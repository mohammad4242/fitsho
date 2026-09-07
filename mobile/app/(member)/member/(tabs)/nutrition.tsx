import { NutritionFoundationScreen } from "../../../../nutrition/NutritionFoundationScreen";
import { RouteGuard } from "../../../../ui/navigation/RouteGuards";

export default function MemberNutritionScreen() {
  return (
    <RouteGuard kind="member" requiredCapability="nutrition">
      <NutritionFoundationScreen />
    </RouteGuard>
  );
}
