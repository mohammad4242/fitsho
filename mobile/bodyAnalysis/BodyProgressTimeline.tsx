import { useEffect, useMemo, useRef, useState } from "react";
import { Image, StyleSheet, Text, View } from "react-native";

import type {
  BodyPhotoSessionState,
  BodyProgressTimelineItem,
} from "@fitician/core/body-photos";

import { Button, Card } from "../ui/components";
import { fiticianTokens } from "../ui/tokens";
import { BodyBeforeAfterComparison } from "./BodyBeforeAfterComparison";
import { BodyProgressComparisonCard } from "./BodyProgressComparison";
import {
  createPrivateBodyPhotoClient,
  loadPrivateBodyPhotoUris,
  type PrivateBodyPhotoUris,
} from "./bodyPhotoPrivateMedia";

type TimelineMedia = {
  readonly after: PrivateBodyPhotoUris;
  readonly before: PrivateBodyPhotoUris;
  readonly latest: PrivateBodyPhotoUris;
};

export function BodyProgressTimeline({
  authDownload,
  items,
  onDelete,
  onOpen,
  onResume,
  userId,
}: {
  readonly authDownload: Parameters<typeof createPrivateBodyPhotoClient>[0];
  readonly items: readonly BodyProgressTimelineItem[];
  readonly onDelete: (item: BodyProgressTimelineItem) => void;
  readonly onOpen: (item: BodyProgressTimelineItem) => void;
  readonly onResume: (item: BodyProgressTimelineItem) => void;
  readonly userId: string | null | undefined;
}) {
  const mediaClient = useMemo(
    () => createPrivateBodyPhotoClient(authDownload, userId),
    [authDownload, userId],
  );
  const [mediaBySession, setMediaBySession] = useState<Record<string, TimelineMedia>>({});
  const hasLoadedMedia = useRef(false);
  const incompleteItems = useMemo(
    () => items.filter((item) => item.session.submitted_at === null),
    [items],
  );
  const analysisItems = useMemo(
    () => items.filter((item) => item.session.submitted_at !== null),
    [items],
  );

  useEffect(() => {
    if (mediaClient === null) {
      if (hasLoadedMedia.current) {
        hasLoadedMedia.current = false;
        setMediaBySession({});
      }
      return undefined;
    }
    let active = true;
    void Promise.all(analysisItems.map(async (item) => {
      const latest = await loadPrivateBodyPhotoUris(
        item.photos,
        mediaClient,
        `body-analysis-${item.session.id}`,
      );
      const before = item.comparison === null
        ? {}
        : await loadPrivateBodyPhotoUris(
          item.comparison.before_photos,
          mediaClient,
          `body-analysis-${item.comparison.previous_session_id}-before`,
        );
      const after = item.comparison === null
        ? {}
        : await loadPrivateBodyPhotoUris(
          item.comparison.after_photos,
          mediaClient,
          `body-analysis-${item.comparison.current_session_id}-after`,
        );
      return [item.session.id, { after, before, latest }] as const;
    })).then((entries) => {
      if (active) {
        hasLoadedMedia.current = true;
        setMediaBySession(Object.fromEntries(entries));
      }
    });
    return () => {
      active = false;
    };
  }, [analysisItems, mediaClient]);

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <View style={styles.headerCopy}>
          <Text style={styles.eyebrow}>نمای طولی</Text>
          <Text accessibilityRole="header" style={styles.headerTitle}>بدن من در گذر زمان</Text>
        </View>
        <Text style={styles.headerIntro}>
          تغییرهای دقیق ثبت‌شده و مشاهده‌های تصویریِ برچسب‌خورده را از اسکن‌های استانداردت دنبال کن.
        </Text>
      </View>

      {incompleteItems.length > 0 ? (
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Text style={styles.eyebrow}>هنوز برای تحلیل ارسال نشده</Text>
            <Text accessibilityRole="header" style={styles.sectionTitle}>نشست‌های ناتمام</Text>
          </View>
          <View style={styles.incompleteList}>
            {incompleteItems.map((item) => (
              <IncompleteSessionCard
                item={item}
                key={item.session.id}
                onDelete={() => onDelete(item)}
                onResume={() => onResume(item)}
              />
            ))}
          </View>
        </View>
      ) : null}

      {analysisItems.length > 0 ? (
        <View accessibilityLabel="روند تحلیل‌های ثبت‌شده" style={styles.timelineList}>
          {analysisItems.map((item, index) => (
            <TimelineItem
              isLatest={index === 0}
              item={item}
              key={item.session.id}
              media={mediaBySession[item.session.id]}
              onDelete={() => onDelete(item)}
              onOpen={() => onOpen(item)}
            />
          ))}
        </View>
      ) : incompleteItems.length === 0 ? (
        <Text style={styles.empty}>هنوز تحلیل بدنی ارسال‌شده‌ای وجود ندارد.</Text>
      ) : null}
    </View>
  );
}

function IncompleteSessionCard({
  item,
  onDelete,
  onResume,
}: {
  readonly item: BodyProgressTimelineItem;
  readonly onDelete: () => void;
  readonly onResume: () => void;
}) {
  return (
    <Card style={styles.incompleteCard}>
      <View style={styles.cardHeading}>
        <Text style={styles.date}>{formatDate(item.session.created_at)}</Text>
        <Text style={styles.status}>{sessionStateLabel(item.session.state)}</Text>
      </View>
      <Text style={styles.meta}>{formatCount(item.photos.length)} / ۳ عکس</Text>
      <View style={styles.actions}>
        <Button label="ادامه نشست" onPress={onResume} variant="secondary" />
        <Button label="حذف بارگذاری" onPress={onDelete} variant="danger" />
      </View>
    </Card>
  );
}

function TimelineItem({
  isLatest,
  item,
  media,
  onDelete,
  onOpen,
}: {
  readonly isLatest: boolean;
  readonly item: BodyProgressTimelineItem;
  readonly media: TimelineMedia | undefined;
  readonly onDelete: () => void;
  readonly onOpen: () => void;
}) {
  const latestPhoto = item.photos.find((photo) => media?.latest[photo.view] !== undefined) ?? item.photos[0];
  const latestPhotoUri = latestPhoto === undefined ? undefined : media?.latest[latestPhoto.view];
  const metrics = item.snapshot === null ? [] : [
    { label: "وزن ثبت‌شده", value: `${formatMetric(item.snapshot.weight_kg)} کیلو` },
    { label: "دور کمر", value: `${formatMetric(item.snapshot.waist_circumference_cm)} سانتی‌متر` },
    { label: "دور شانه", value: `${formatMetric(item.snapshot.shoulder_circumference_cm)} سانتی‌متر` },
    { label: "دور باسن", value: `${formatMetric(item.snapshot.hip_circumference_cm)} سانتی‌متر` },
  ];

  return (
    <View style={styles.timelineItem}>
      <View style={[styles.timelineRail, isLatest && styles.timelineRailLatest]} />
      <View style={[styles.timelineNode, isLatest && styles.timelineNodeLatest]} />
      <View style={styles.timelineArticle}>
        <View style={styles.cardHeading}>
          <View style={styles.dateBlock}>
            {isLatest ? <Text style={styles.latest}>آخرین اسکن</Text> : null}
            <Text style={styles.date}>{formatDate(item.session.created_at)}</Text>
            <Text style={styles.status}>{sessionStateLabel(item.session.state)}</Text>
          </View>
          <Text style={styles.meta}>{formatCount(item.photos.length)} / ۳ عکس</Text>
        </View>

        {isLatest ? (
          <View style={styles.latestPhoto}>
            {latestPhotoUri === undefined ? (
              <View style={styles.privatePlaceholder}>
                <Text style={styles.protectedLabel}>محافظت‌شده</Text>
              </View>
            ) : (
              <Image
                accessibilityLabel="آخرین عکس پیشرفت"
                accessibilityIgnoresInvertColors
                resizeMode="contain"
                source={{ uri: latestPhotoUri }}
                style={styles.latestImage}
              />
            )}
          </View>
        ) : null}

        <View accessibilityLabel="وضعیت بررسی متخصصان" style={styles.reviewGrid}>
          <ReviewBadge decision={item.review_state.coach.decision} label="مربی" />
          <ReviewBadge decision={item.review_state.doctor.decision} label="پزشک" />
        </View>

        {isLatest && item.snapshot !== null ? (
          <View style={styles.snapshot}>
            <View style={styles.snapshotHeader}>
              <Text style={styles.snapshotTitle}>اندازه‌گیری‌های این اسکن</Text>
              <Text style={styles.snapshotProvenance}>هنگام تأیید این اسکن توسط تو ثبت شده است.</Text>
            </View>
            <View style={styles.metricGrid}>
              {metrics.map((metric) => (
                <View key={metric.label} style={styles.metricCard}>
                  <Text style={styles.metricLabel}>{metric.label}</Text>
                  <Text style={styles.metricValue}>{metric.value}</Text>
                </View>
              ))}
            </View>
          </View>
        ) : null}

        <View style={styles.actions}>
          <Button label="مشاهده نتیجه" onPress={onOpen} variant="secondary" />
          <Button label="حذف تحلیل" onPress={onDelete} variant="danger" />
        </View>

        {item.comparison !== null ? (
          <>
            <BodyProgressComparisonCard comparison={item.comparison} />
            <BodyBeforeAfterComparison
              afterPhotoUris={media?.after ?? {}}
              afterPhotos={item.comparison.after_photos}
              beforePhotoUris={media?.before ?? {}}
              beforePhotos={item.comparison.before_photos}
              currentDate={formatDate(item.comparison.current_session_date)}
              previousDate={formatDate(item.comparison.previous_session_date)}
            />
          </>
        ) : null}
      </View>
    </View>
  );
}

function ReviewBadge({
  decision,
  label,
}: {
  readonly decision: string | null;
  readonly label: string;
}) {
  return (
    <View style={styles.reviewBadge}>
      <View style={styles.reviewCopy}>
        <Text style={styles.reviewTitle}>{label}</Text>
        <Text style={styles.reviewState}>{reviewLabel(decision)}</Text>
      </View>
      <View style={[styles.reviewDot, decision === "approved" && styles.reviewDotApproved]} />
    </View>
  );
}

function formatCount(value: number): string {
  return new Intl.NumberFormat("fa-IR").format(value);
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("fa-IR", { dateStyle: "medium" }).format(new Date(value));
}

function formatMetric(value: number): string {
  return new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 1 }).format(value);
}

function reviewLabel(decision: string | null): string {
  if (decision === "approved") return "تأیید شد";
  if (decision === "changes_required") return "نیازمند اصلاح";
  if (decision === "rejected") return "رد شد";
  return "در انتظار";
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
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
  cardHeading: {
    alignItems: "flex-start",
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
    justifyContent: "space-between",
  },
  container: {
    gap: fiticianTokens.spacing[5],
  },
  date: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  dateBlock: {
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  empty: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 23,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  eyebrow: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  header: {
    gap: fiticianTokens.spacing[2],
  },
  headerCopy: {
    gap: fiticianTokens.spacing[1],
  },
  headerIntro: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 23,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  headerTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h2,
    lineHeight: 32,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  incompleteCard: {
    gap: fiticianTokens.spacing[3],
  },
  incompleteList: {
    gap: fiticianTokens.spacing[3],
  },
  latest: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  latestImage: {
    height: "100%",
    width: "100%",
  },
  latestPhoto: {
    alignSelf: "flex-start",
    backgroundColor: fiticianTokens.colors.canvas,
    borderRadius: fiticianTokens.radii.medium,
    height: 132,
    overflow: "hidden",
    position: "relative",
    width: 96,
  },
  meta: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  metricCard: {
    backgroundColor: fiticianTokens.colors.surfaceRaised,
    borderRadius: fiticianTokens.radii.small,
    flexBasis: "46%",
    flexGrow: 1,
    gap: fiticianTokens.spacing[1],
    minWidth: "46%",
    padding: fiticianTokens.spacing[3],
  },
  metricGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
  metricLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 11,
    lineHeight: 18,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  metricValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    lineHeight: 21,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  protectedLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 10,
    textAlign: "center",
    writingDirection: "rtl",
  },
  privatePlaceholder: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    flex: 1,
    justifyContent: "center",
    padding: fiticianTokens.spacing[2],
  },
  reviewBadge: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
    padding: fiticianTokens.spacing[3],
  },
  reviewCopy: {
    alignItems: "stretch",
    gap: 2,
  },
  reviewDot: {
    backgroundColor: fiticianTokens.colors.muted,
    borderRadius: fiticianTokens.radii.pill,
    height: 8,
    width: 8,
  },
  reviewDotApproved: {
    backgroundColor: fiticianTokens.colors.success,
  },
  reviewGrid: {
    gap: fiticianTokens.spacing[2],
  },
  reviewState: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 11,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  reviewTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  section: {
    gap: fiticianTokens.spacing[3],
  },
  sectionHeader: {
    gap: fiticianTokens.spacing[1],
  },
  sectionTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 29,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  snapshot: {
    backgroundColor: "rgba(80,223,206,0.05)",
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.large,
    borderWidth: 1,
    gap: fiticianTokens.spacing[3],
    padding: fiticianTokens.spacing[3],
  },
  snapshotHeader: {
    gap: fiticianTokens.spacing[1],
  },
  snapshotProvenance: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 19,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  snapshotTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  status: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  timelineArticle: {
    backgroundColor: fiticianTokens.colors.surface,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.extraLarge,
    borderWidth: 1,
    gap: fiticianTokens.spacing[3],
    padding: fiticianTokens.spacing[3],
  },
  timelineItem: {
    paddingRight: 24,
    position: "relative",
  },
  timelineList: {
    gap: fiticianTokens.spacing[4],
  },
  timelineNode: {
    backgroundColor: fiticianTokens.colors.muted,
    borderColor: fiticianTokens.colors.canvas,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 3,
    height: 14,
    position: "absolute",
    right: 1,
    top: 22,
    width: 14,
    zIndex: 2,
  },
  timelineNodeLatest: {
    backgroundColor: fiticianTokens.colors.aqua,
  },
  timelineRail: {
    backgroundColor: fiticianTokens.colors.lineStrong,
    bottom: 0,
    position: "absolute",
    right: 7,
    top: 0,
    width: 2,
  },
  timelineRailLatest: {
    backgroundColor: fiticianTokens.colors.aqua,
  },
});
