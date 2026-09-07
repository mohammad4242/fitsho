import { RouteEntryScreen } from "../../../../ui/navigation/RouteEntryScreen";
import { RouteGuard } from "../../../../ui/navigation/RouteGuards";

export default function MemberWorkoutsScreen() {
  return (
    <RouteGuard kind="member" requiredCapability="training">
      <RouteEntryScreen description="برنامه‌های تمرینی و اجرای جلسه‌ها" title="تمرین" />
    </RouteGuard>
  );
}
