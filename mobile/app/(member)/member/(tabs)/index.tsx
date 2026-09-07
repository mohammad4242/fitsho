import { useRouter } from "expo-router";

import { Button } from "../../../../ui/components";
import { RouteEntryScreen } from "../../../../ui/navigation/RouteEntryScreen";

export default function MemberHomeScreen() {
  const router = useRouter();
  return (
    <RouteEntryScreen description="برنامه امروز و پیشرفت شما" title="خانه">
      <Button label="تحلیل بدن" onPress={() => router.push("/member/body-analysis")} />
    </RouteEntryScreen>
  );
}
