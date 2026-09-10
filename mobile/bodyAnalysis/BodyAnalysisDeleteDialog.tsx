import { Modal, Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import type { BodyProgressTimelineItem, BodyPhotoSessionState } from "@fitician/core/body-photos";

import { AppIcon, Button } from "../ui/components";
import { fiticianTokens } from "../ui/tokens";

export function BodyAnalysisDeleteDialog({
  busy,
  error,
  item,
  onClose,
  onConfirm,
}: {
  readonly busy: boolean;
  readonly error?: string | null;
  readonly item: BodyProgressTimelineItem | null;
  readonly onClose: () => void;
  readonly onConfirm: () => void;
}) {
  if (item === null) return null;
  const incomplete = item.session.submitted_at === null;
  const title = incomplete ? "بارگذاری ناتمام حذف شود؟" : "تحلیل ثبت‌شده حذف شود؟";

  return (
    <Modal
      accessibilityViewIsModal
      accessibilityLabel={title}
      animationType="fade"
      onRequestClose={onClose}
      statusBarTranslucent
      transparent
      visible
    >
      <SafeAreaView style={styles.overlay}>
        <Pressable accessibilityRole="button" accessibilityLabel="بستن پنجره حذف" onPress={onClose} style={StyleSheet.absoluteFill} />
        <View style={styles.dialog}>
          <View style={styles.rail} />
          <View style={styles.header}>
            <View style={styles.headerCopy}>
              <Text style={styles.eyebrow}>حذف از Body Analysis</Text>
              <Text accessibilityRole="header" style={styles.title}>{title}</Text>
            </View>
            <View style={styles.iconTile}>
              <AppIcon color={fiticianTokens.colors.danger} name="delete" size={24} />
            </View>
          </View>
          <Text style={styles.description}>
            {incomplete
              ? "عکس‌های ذخیره‌شده و این جلسه بارگذاری برای همیشه حذف می‌شوند."
              : "عکس‌های ذخیره‌شده و این جلسه تحلیل برای همیشه حذف می‌شوند."}
          </Text>
          <View style={styles.metaGrid}>
            <View style={styles.metaCard}>
              <Text style={styles.metaLabel}>تاریخ جلسه</Text>
              <Text style={styles.metaValue}>{formatDate(item.session.created_at)}</Text>
            </View>
            <View style={styles.metaCard}>
              <Text style={styles.metaLabel}>وضعیت فعلی</Text>
              <Text style={styles.metaValue}>{sessionStateLabel(item.session.state)}</Text>
            </View>
          </View>
          {error !== undefined && error !== null ? <Text accessibilityRole="alert" style={styles.error}>{error}</Text> : null}
          <View style={styles.actions}>
            <Button
              disabled={busy}
              label={busy ? "در حال حذف…" : "حذف دائمی"}
              onPress={onConfirm}
              variant="danger"
            />
            <Button disabled={busy} label="نگه‌داشتن جلسه" onPress={onClose} variant="ghost" />
          </View>
        </View>
      </SafeAreaView>
    </Modal>
  );
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("fa-IR", { dateStyle: "medium" }).format(new Date(value));
}

function sessionStateLabel(state: BodyPhotoSessionState): string {
  const labels: Record<BodyPhotoSessionState, string> = {
    analyzing: "در حال تحلیل",
    awaiting_consent: "در انتظار رضایت",
    completed: "تکمیل‌شده",
    deleted: "حذف‌شده",
    draft: "پیش‌نویس",
    failed: "ناموفق",
    queued: "در صف تحلیل",
    review_pending: "در انتظار بررسی تخصصی",
    uploaded: "تصاویر ثبت‌شده",
    uploading: "در حال بارگذاری",
    validating: "در حال بررسی کیفیت",
  };
  return labels[state];
}

const styles = StyleSheet.create({
  actions: {
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
    marginTop: fiticianTokens.spacing[4],
  },
  description: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 25,
    textAlign: "right",
    writingDirection: "rtl",
  },
  dialog: {
    backgroundColor: fiticianTokens.colors.surface,
    borderColor: fiticianTokens.colors.danger,
    borderRadius: fiticianTokens.radii.extraLarge,
    borderWidth: 1,
    elevation: fiticianTokens.shadows.focus.elevation,
    maxWidth: 520,
    overflow: "hidden",
    padding: fiticianTokens.spacing[5],
    shadowColor: "#000000",
    shadowOpacity: 0.48,
    shadowRadius: 24,
    width: "100%",
  },
  error: {
    color: fiticianTokens.colors.danger,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 20,
    textAlign: "right",
    writingDirection: "rtl",
  },
  eyebrow: {
    color: fiticianTokens.colors.danger,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  header: {
    alignItems: "center",
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
  },
  headerCopy: {
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  iconTile: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.dangerSurface,
    borderColor: fiticianTokens.colors.danger,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    height: 50,
    justifyContent: "center",
    width: 50,
  },
  metaCard: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    flex: 1,
    gap: fiticianTokens.spacing[1],
    padding: fiticianTokens.spacing[3],
  },
  metaGrid: {
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
  },
  metaLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  metaValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    lineHeight: 19,
    textAlign: "right",
    writingDirection: "rtl",
  },
  overlay: {
    alignItems: "center",
    backgroundColor: "rgba(2,6,7,0.78)",
    flex: 1,
    justifyContent: "center",
    padding: fiticianTokens.spacing[4],
  },
  rail: {
    backgroundColor: fiticianTokens.colors.danger,
    bottom: 0,
    left: 0,
    position: "absolute",
    shadowColor: fiticianTokens.colors.danger,
    shadowOpacity: 0.55,
    shadowRadius: 20,
    top: 0,
    width: 5,
  },
  title: {
    color: fiticianTokens.colors.ink,
    flexShrink: 1,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 29,
    textAlign: "right",
    writingDirection: "rtl",
  },
});
