import { Stack, usePathname } from "expo-router";

import { RouteGuard } from "../../ui/navigation/RouteGuards";
import { isTokenAuthPath } from "../../ui/navigation/authRoute";

export default function AuthLayout() {
  const pathname = usePathname();
  const stack = <Stack screenOptions={{ headerShown: false }} />;
  return isTokenAuthPath(pathname) ? stack : <RouteGuard kind="auth">{stack}</RouteGuard>;
}
