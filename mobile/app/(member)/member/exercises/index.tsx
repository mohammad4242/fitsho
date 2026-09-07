import { ExerciseCatalogScreen } from "../../../../exercises/ExerciseCatalogScreen";
import { RouteGuard } from "../../../../ui/navigation/RouteGuards";

export default function MemberExerciseCatalogRoute() {
  return (
    <RouteGuard kind="member" requiredCapability="training">
      <ExerciseCatalogScreen />
    </RouteGuard>
  );
}
