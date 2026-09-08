import { usePathname, useRouter } from "expo-router";
import { StyleSheet, View } from "react-native";

import { Button } from "../ui/components/Button";
import { fiticianTokens } from "../ui/tokens";

declare const __DEV__: boolean | undefined;

export function E2ERoleNavigator() {
  const pathname = usePathname();
  const router = useRouter();
  const enabled = typeof __DEV__ !== "undefined" && __DEV__ && process.env.EXPO_PUBLIC_E2E === "1";

  if (!enabled || pathname !== "/member") {
    return null;
  }

  return (
    <View accessibilityLabel="E2E role navigation" style={styles.container}>
      <Button label="E2E: مربی" onPress={() => router.replace("/coach")} variant="secondary" />
      <Button label="E2E: پزشک" onPress={() => router.replace("/physician")} variant="secondary" />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: fiticianTokens.colors.surface,
    bottom: fiticianTokens.spacing[4],
    gap: fiticianTokens.spacing[2],
    left: fiticianTokens.spacing[4],
    padding: fiticianTokens.spacing[2],
    position: "absolute",
    right: fiticianTokens.spacing[4],
    zIndex: 10,
  },
});
