import { RouteEntryScreen } from "../../../../ui/navigation/RouteEntryScreen";
import { RouteGuard } from "../../../../ui/navigation/RouteGuards";

export default function MemberNutritionScreen() {
  return (
    <RouteGuard kind="member" requiredCapability="nutrition">
      <RouteEntryScreen description="برنامه غذایی و ثبت وعده‌ها" title="تغذیه" />
    </RouteGuard>
  );
}
