import { useCallback, useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Linking, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { getMobileRuntimeConfig } from "../config/nativeRuntimeConfig";
import { useAndroidBackHandler } from "../ui/navigation/BackBehaviorProvider";
import { Button, Card, Notice, PageHeading, TextField } from "../ui/components";
import { Screen } from "../ui/layout";
import { fiticianTokens } from "../ui/tokens";
import {
  createAccountDeletionApi,
  type AccountDeletionStatusResponse,
} from "./accountDeletionApi";
import {
  accountDeletionError,
  formatDeletionDate,
  isExactDeletionConfirmation,
} from "./accountDeletionModel";

export function AccountDeletionScreen() {
  const auth = useMobileAuth();
  const router = useRouter();
  const runtime = useMemo(getMobileRuntimeConfig, []);
  const api = useMemo(() => createAccountDeletionApi(auth.request), [auth.request]);
  const [status, setStatus] = useState<AccountDeletionStatusResponse | null>(null);
  const [confirmation, setConfirmation] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const canSubmit = confirmation === "DELETE";

  const loadStatus = useCallback(async () => {
    if (auth.status !== "signed_in") {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setStatus(await api.getStatus());
    } catch (loadError) {
      setError(accountDeletionError(loadError).message);
    } finally {
      setLoading(false);
    }
  }, [api, auth.status]);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  useAndroidBackHandler(
    "wizard",
    () => {
      if (busy) return true;
      if (router.canGoBack()) {
        router.back();
        return true;
      }
      return false;
    },
    true,
  );

  async function submitDeletion() {
    if (busy) return;
    if (!isExactDeletionConfirmation(confirmation)) {
      setError("برای ادامه باید عبارت DELETE را دقیق وارد کنی.");
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const next = await api.requestDeletion("DELETE", password === "" ? undefined : password);
      setStatus(next);
      setConfirmation("");
      setPassword("");
      setMessage("درخواست حذف ثبت شد. تا پایان مهلت لغو، امکان بازگرداندن آن وجود دارد.");
    } catch (requestError) {
      await handleRequestError(requestError);
    } finally {
      setBusy(false);
    }
  }

  async function cancelDeletion() {
    if (busy) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      setStatus(await api.cancelDeletion());
      setMessage("درخواست حذف لغو شد و حساب باقی می‌ماند.");
    } catch (requestError) {
      await handleRequestError(requestError);
    } finally {
      setBusy(false);
    }
  }

  async function handleRequestError(requestError: unknown) {
    const mapped = accountDeletionError(requestError);
    setError(mapped.message);
    if (mapped.requiresReauthentication) {
      await auth.logout().catch(() => undefined);
      router.replace("/auth/sign-in");
    }
  }

  async function openExternal(path: "/privacy" | "/delete-account") {
    try {
      await Linking.openURL(`${runtime.frontendOrigin}${path}`);
    } catch {
      setError("صفحهٔ وب باز نشد. بعداً دوباره تلاش کن.");
    }
  }

  if (loading) {
    return (
      <Screen contentWidth="reading" contentContainerStyle={styles.centered}>
        <ActivityIndicator accessibilityLabel="در حال بارگذاری" color={fiticianTokens.colors.aqua} />
        <Text style={styles.muted}>در حال دریافت وضعیت حذف حساب…</Text>
      </Screen>
    );
  }

  return (
    <Screen contentWidth="reading" contentContainerStyle={styles.screen}>
      <View style={styles.brandRow}>
        <Button label="بازگشت" onPress={() => router.back()} variant="ghost" />
        <Text style={styles.brand}>FITICIAN</Text>
      </View>
      <PageHeading
        compact={false}
        eyebrow="حساب / Account"
        supportingText="درخواست حذف حساب را از همین صفحه ثبت کن. این مسیر برای اعضای فیتشو، خارج از اپلیکیشن هم در دسترس است."
        testID="account-deletion-heading"
        title="حذف حساب فیتشو"
      />

      {error !== null ? <Notice actionLabel="تلاش دوباره" message={error} onAction={() => void loadStatus()} variant="danger" /> : null}
      {message !== null ? <Notice message={message} variant="success" /> : null}

      <Card style={styles.policyCard}>
        <Text style={styles.sectionTitle}>قبل از ثبت درخواست</Text>
        <Text style={styles.body}>پروفایل، برنامه‌ها، عکس‌های خصوصی، داده‌های تغذیه و پرونده‌های شخصی حذف می‌شوند.</Text>
        <Text style={styles.body}>اطلاعات حداقلی عملیاتی فقط مطابق ماتریس نگهداری مصوب باقی می‌ماند.</Text>
      </Card>

      {status?.status === "pending" ? (
        <Card style={styles.pendingCard} variant="raised">
          <Text style={styles.sectionTitle}>حساب برای حذف زمان‌بندی شد</Text>
          <Text style={styles.body}>تا پیش از این زمان می‌توانی درخواست را لغو کنی: {formatDeletionDate(status.grace_period_ends_at)}</Text>
          <Button
            disabled={busy}
            label="لغو درخواست حذف"
            loading={busy}
            onPress={() => void cancelDeletion()}
            variant="secondary"
          />
        </Card>
      ) : status?.status === "completed" ? (
        <Card style={styles.pendingCard} variant="raised">
          <Text style={styles.sectionTitle}>این حساب قبلاً حذف شده است.</Text>
        </Card>
      ) : (
        <Card style={styles.formCard}>
          {status?.status === "cancelled" ? (
            <Notice message="درخواست حذف لغو شد. اگر هنوز می‌خواهی حسابت حذف شود، می‌توانی درخواست تازه‌ای ثبت کنی." variant="info" />
          ) : null}
          <Text style={styles.body}>حذف پس از پایان مهلت بازگشت که بعد از ثبت نمایش داده می‌شود، اجرا خواهد شد.</Text>
          <TextField
            autoCapitalize="characters"
            autoCorrect={false}
            label="تأیید حذف"
            onChangeText={setConfirmation}
            placeholder="DELETE"
            textDirection="ltr"
            value={confirmation}
          />
          <TextField
            autoCapitalize="none"
            autoCorrect={false}
            label="رمز عبور، اگر حساب رمزدار است"
            onChangeText={setPassword}
            secureTextEntry
            textDirection="ltr"
            value={password}
          />
          <Button
            disabled={busy || !canSubmit}
            label="ثبت درخواست حذف"
            loading={busy}
            onPress={() => void submitDeletion()}
            variant="danger"
          />
        </Card>
      )}

      <Card style={styles.linksCard}>
        <Text style={styles.sectionTitle}>دسترسی خارج از برنامه</Text>
        <Text style={styles.body}>اگر به برنامه دسترسی نداری، همین فرایند از صفحهٔ وب هم در دسترس است.</Text>
        <Button label="صفحه حذف حساب در وب" onPress={() => void openExternal("/delete-account")} variant="secondary" />
        <Button label="حریم خصوصی در وب" onPress={() => void openExternal("/privacy")} variant="ghost" />
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  body: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    lineHeight: 27,
    textAlign: "right",
    writingDirection: "rtl",
  },
  brand: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.displayEnglish,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    letterSpacing: 1.4,
    writingDirection: "ltr",
  },
  centered: {
    alignItems: "center",
    gap: fiticianTokens.spacing[3],
    justifyContent: "center",
  },
  formCard: { gap: fiticianTokens.spacing[4] },
  linksCard: { gap: fiticianTokens.spacing[3] },
  muted: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    writingDirection: "rtl",
  },
  pendingCard: { gap: fiticianTokens.spacing[3] },
  policyCard: { gap: fiticianTokens.spacing[3] },
  brandRow: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
    width: "100%",
  },
  screen: { gap: fiticianTokens.spacing[4] },
  sectionTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    textAlign: "right",
    writingDirection: "rtl",
  },
});
