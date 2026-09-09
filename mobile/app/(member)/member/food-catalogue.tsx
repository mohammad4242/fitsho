import { NutritionCatalogueSection } from "../../../nutrition/NutritionCatalogueSection";
import { Screen } from "../../../ui/layout";
import { RouteGuard } from "../../../ui/navigation/RouteGuards";

export default function MemberFoodCatalogueRoute() {
  return (
    <RouteGuard kind="member" requiredCapability="nutrition">
      <Screen contentWidth="reading">
        <NutritionCatalogueSection initialMode="foods" />
      </Screen>
    </RouteGuard>
  );
}
