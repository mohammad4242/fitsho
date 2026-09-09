import { Linking, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";

import { getMobileRuntimeConfig } from "../config/nativeRuntimeConfig";
import { Button } from "../ui/components";
import { fiticianTokens } from "../ui/tokens";

export function AccountPrivacyLinks() {
  const router = useRouter();
  const runtime = getMobileRuntimeConfig();

  function openPrivacyPolicy() {
    void Linking.openURL(`${runtime.frontendOrigin}/privacy`).catch(() => undefined);
  }

  return (
    <View style={styles.links}>
      <Button
        label="حذف حساب"
        onPress={() => router.push("/account-deletion")}
        variant="secondary"
      />
      <Button label="سیاست حریم خصوصی در وب" onPress={openPrivacyPolicy} variant="ghost" />
    </View>
  );
}

const styles = StyleSheet.create({
  links: {
    gap: fiticianTokens.spacing[2],
    marginTop: fiticianTokens.spacing[5],
  },
});
