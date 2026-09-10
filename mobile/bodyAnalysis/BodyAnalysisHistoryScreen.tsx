import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "expo-router";
import { StyleSheet, Text, View } from "react-native";

import type { BodyProgressTimelineItem, BodyProgressTimelineResponse } from "@fitician/core/body-photos";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { Button, Notice, Skeleton } from "../ui/components";
import { Screen } from "../ui/layout";
import { fiticianTokens } from "../ui/tokens";
import { BodyAnalysisDeleteDialog } from "./BodyAnalysisDeleteDialog";
import { BodyAnalysisEmptyState } from "./BodyAnalysisEmptyState";
import { BodyAnalysisLandingHero } from "./BodyAnalysisLandingHero";
import { BodyAnalysisStartCard } from "./BodyAnalysisStartCard";
import { createBodyPhotoApi } from "./bodyPhotoApi";
import { BodyProgressTimeline } from "./BodyProgressTimeline";

export interface BodyAnalysisHistoryScreenProps {
  readonly tabRoot?: boolean;
}

export function BodyAnalysisHistoryScreen({ tabRoot = false }: BodyAnalysisHistoryScreenProps = {}) {
  const auth = useMobileAuth();
  const router = useRouter();
  const api = useMemo(
    () => createBodyPhotoApi(auth.request, auth.upload, auth.download),
    [auth.download, auth.request, auth.upload],
  );
  const [timeline, setTimeline] = useState<BodyProgressTimelineResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<BodyProgressTimelineItem | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const loadTimeline = useCallback(async () => {
    setFailed(false);
    try {
      setTimeline(await api.getTimeline());
    } catch {
      setFailed(true);
    }
  }, [api]);

  useEffect(() => {
    void loadTimeline();
  }, [loadTimeline]);

  function openDeleteDialog(item: BodyProgressTimelineItem) {
    setDeleteError(null);
    setDeleteTarget(item);
  }

  function closeDeleteDialog() {
    if (busy) return;
    setDeleteError(null);
    setDeleteTarget(null);
  }

  async function deleteTargetSession() {
    if (deleteTarget === null || busy) return;
    setBusy(true);
    setDeleteError(null);
    try {
      await api.deleteSession(deleteTarget.session.id);
      setTimeline((current) => current === null
        ? current
        : { ...current, items: current.items.filter((item) => item.session.id !== deleteTarget.session.id) });
      setDeleteTarget(null);
    } catch {
      setDeleteError("جلسه حذف نشد. دوباره تلاش کن.");
    } finally {
      setBusy(false);
    }
  }

  function startNewSession() {
    router.push("/member/body-analysis-capture");
  }

  return (
    <Screen contentContainerStyle={styles.screen}>
      <BodyAnalysisLandingHero />

      {timeline === null && !failed ? (
        <View style={styles.loading}>
          <Skeleton accessibilityLabel="در حال بارگذاری تاریخچه تحلیل بدن" height={34} width="68%" />
          <Skeleton accessibilityLabel="در حال بارگذاری تاریخچه تحلیل بدن" height={150} />
        </View>
      ) : null}

      {failed ? (
        <View style={styles.statusState}>
          <Text accessibilityRole="header" style={styles.statusTitle}>تاریخچه تحلیل بدن در دسترس نیست</Text>
          <Notice message="دریافت نشست‌های تحلیل انجام نشد." variant="danger" />
          <Button label="تلاش دوباره" onPress={() => void loadTimeline()} />
        </View>
      ) : null}

      {timeline !== null && timeline.items.length === 0 ? (
        <BodyAnalysisEmptyState onStart={startNewSession} />
      ) : null}

      {timeline !== null && timeline.items.length > 0 ? (
        <View style={styles.populatedContent}>
          <BodyAnalysisStartCard onStart={startNewSession} sessionCount={timeline.items.length} />
          <BodyProgressTimeline
            authDownload={auth.download}
            items={timeline.items}
            onDelete={openDeleteDialog}
            onOpen={(item) => router.push(`/member/body-analysis-result/${encodeURIComponent(item.session.id)}`)}
            onResume={(item) => router.push({
              pathname: "/member/body-analysis-capture",
              params: { sessionId: item.session.id },
            })}
            userId={auth.user?.id}
          />
        </View>
      ) : null}

      {!tabRoot ? <Button label="بازگشت" onPress={() => router.replace("/member")} variant="ghost" /> : null}

      <BodyAnalysisDeleteDialog
        busy={busy}
        error={deleteError}
        item={deleteTarget}
        onClose={closeDeleteDialog}
        onConfirm={() => void deleteTargetSession()}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  loading: {
    gap: fiticianTokens.spacing[4],
    paddingVertical: fiticianTokens.spacing[5],
  },
  populatedContent: {
    gap: fiticianTokens.spacing[5],
  },
  screen: {
    gap: fiticianTokens.spacing[5],
    paddingBottom: fiticianTokens.spacing[7],
    paddingTop: fiticianTokens.spacing[3],
  },
  statusState: {
    gap: fiticianTokens.spacing[3],
  },
  statusTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 29,
    textAlign: "right",
    writingDirection: "rtl",
  },
});
