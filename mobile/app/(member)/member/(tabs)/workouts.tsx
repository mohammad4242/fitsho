import { RouteGuard } from "../../../../ui/navigation/RouteGuards";
import { WorkoutPlansScreen } from "../../../../workouts/WorkoutPlansScreen";

export default function MemberWorkoutsScreen() {
  return (
    <RouteGuard kind="member" requiredCapability="training">
      <WorkoutPlansScreen />
    </RouteGuard>
  );
}
