import { ExerciseDetailScreen } from "../../../../exercises/ExerciseDetailScreen";
import { RouteGuard } from "../../../../ui/navigation/RouteGuards";

export default function MemberExerciseDetailRoute() {
  return (
    <RouteGuard kind="member" requiredCapability="training">
      <ExerciseDetailScreen />
    </RouteGuard>
  );
}
