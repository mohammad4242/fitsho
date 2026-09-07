import { useRouter } from "expo-router";

import { RouteEntryScreen } from "../../../../ui/navigation/RouteEntryScreen";
import { RouteGuard } from "../../../../ui/navigation/RouteGuards";
import { Button } from "../../../../ui/components";

export default function MemberWorkoutsScreen() {
  const router = useRouter();
  return (
    <RouteGuard kind="member" requiredCapability="training">
      <RouteEntryScreen description="برنامه‌های تمرینی و اجرای جلسه‌ها" title="تمرین">
        <Button
          label="کتابخانه حرکات"
          onPress={() => router.push("/member/exercises")}
          variant="secondary"
        />
      </RouteEntryScreen>
    </RouteGuard>
  );
}
