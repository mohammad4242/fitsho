import { useState } from "react";
import {
  Image,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import type { BodyAnalysisExperienceV4, BodyPhotoView } from "@fitician/core/body-photos";

import { AppIcon, Card, MetricRing, ProgressBar, SectionHeader } from "../ui/components";
import { fiticianTokens } from "../ui/tokens";
import {
  buildBodyAnalysisExperienceCopy,
  bodyBmiLabel,
  bodyMetricProgress,
  buildBodyIndicatorSummary,
  type BodyIndicatorPresentation,
  type BodyIndicatorTone,
} from "./bodyAnalysisPresentation";
import { bodyResultAssets } from "./bodyAnalysisAssets";
import { bodyAnalysisCopy } from "./bodyAnalysisCopy";

const viewLabels: Record<BodyPhotoView, string> = {
  back: "پشت",
  front: "روبه‌رو",
  side: "نیم‌رخ",
};

const toneColors: Record<BodyIndicatorTone, string> = {
  amber: fiticianTokens.colors.amber,
  aqua: fiticianTokens.colors.aqua,
  blue: fiticianTokens.colors.blue,
};

export function BodyAnalysisOverviewCard({
  experience,
}: {
  readonly experience: BodyAnalysisExperienceV4;
}) {
  const [activeView, setActiveView] = useState<BodyPhotoView>("front");
  const sex = experience.input_snapshot.sex === "female" ? "female" : "male";
  const sexLabel = sex === "female" ? "زن" : "مرد";
  const bodyFat = experience.body_composition.estimated_body_fat_percent;
  const bmi = experience.body_composition.bmi;
  const indicators = buildBodyIndicatorSummary(experience);
  const experienceCopy = buildBodyAnalysisExperienceCopy(experience);

  return (
    <View style={styles.container}>
      <SectionHeader eyebrow="اسکن و شاخص‌ها" title={bodyAnalysisCopy.topOverview.title} />
      <Card variant="hero" style={styles.heroCard}>
        <View style={styles.heroHeader}>
          <View style={styles.heroCopy}>
            <Text style={styles.heroEyebrow}>BODY SCAN</Text>
            <Text style={styles.heroTitle}>بدن، نقطه شروع مسیر تو</Text>
          </View>
          <View style={styles.captureBadge}>
            <Text style={styles.captureText}>۳ نمای استاندارد</Text>
            <View style={styles.captureDot} />
          </View>
        </View>

        <View style={styles.mediaFrame}>
          <View style={styles.mediaGlow} />
          <Image
            accessibilityLabel={`نمای ${viewLabels[activeView]} آنالیز بدن ${sexLabel}`}
            resizeMode="contain"
            source={bodyResultAssets.overview[sex][activeView]}
            style={styles.bodyImage}
            testID="body-analysis-overview-image"
          />
          <View style={styles.mediaTag}>
            <Text style={styles.mediaTagText}>{viewLabels[activeView]}</Text>
            <AppIcon accessibilityLabel="نمای بدن" color={fiticianTokens.colors.aqua} name="bodyAnalysis" size={16} />
          </View>
        </View>

        <View accessibilityRole="tablist" style={styles.viewTabs}>
          {(["front", "side", "back"] as const).map((view) => (
            <Pressable
              accessibilityLabel={`نمای ${viewLabels[view]}`}
              accessibilityRole="tab"
              accessibilityState={{ selected: activeView === view }}
              key={view}
              onPress={() => setActiveView(view)}
              style={({ pressed }) => [
                styles.viewTab,
                activeView === view && styles.viewTabActive,
                pressed && styles.viewTabPressed,
              ]}
            >
              <Text style={[styles.viewTabText, activeView === view && styles.viewTabTextActive]}>
                {viewLabels[view]}
              </Text>
              <AppIcon
                color={activeView === view ? fiticianTokens.colors.canvas : fiticianTokens.colors.muted}
                name="bodyAnalysis"
                size={17}
              />
            </Pressable>
          ))}
        </View>
      </Card>

      <View style={styles.metricGrid}>
        <BodyMetricCard
          badge={bodyAnalysisCopy.topOverview.bodyFatMethod}
          info={bodyAnalysisCopy.topOverview.infoTooltipBodyFat}
          label={bodyAnalysisCopy.topOverview.bodyFatTitle}
          progress={bodyMetricProgress(bodyFat, 10, 35)}
          trackHint={bodyAnalysisCopy.topOverview.estimateNotice}
          value={bodyFat === null ? "—" : `${formatMetric(bodyFat)}٪`}
        />
        <BodyMetricCard
          badge={bmi === null ? "" : bodyBmiLabel(bmi)}
          info={bodyAnalysisCopy.topOverview.infoTooltipBmi}
          label={bodyAnalysisCopy.topOverview.bmiTitle}
          progress={bodyMetricProgress(bmi, 15, 35)}
          trackHint={bodyAnalysisCopy.topOverview.bmiCategory}
          value={bmi === null ? "—" : formatMetric(bmi)}
        />
      </View>

      <Card variant="glass" style={styles.impressionCard}>
        <View style={styles.cardHeading}>
          <View style={styles.headingCopy}>
            <Text style={styles.cardTitle}>{experienceCopy.firstLookTitle}</Text>
          </View>
          <View style={styles.iconTile}>
            <AppIcon color={fiticianTokens.colors.aqua} name="bodyAnalysis" size={20} />
          </View>
        </View>
        <Text style={styles.body}>{experienceCopy.firstLook}</Text>
        {experienceCopy.route ? <Text style={styles.route}>{experienceCopy.route}</Text> : null}
      </Card>

      <View style={styles.indicatorSection}>
        <SectionHeader eyebrow="نشانه‌های کاربردی" title="شاخص‌های بصری بدن" />
        <View style={styles.indicatorGrid}>
          {indicators.map((indicator) => (
            <IndicatorCard indicator={indicator} key={indicator.id} />
          ))}
        </View>
      </View>
    </View>
  );
}

function BodyMetricCard({
  badge,
  info,
  label,
  progress,
  trackHint,
  value,
}: {
  readonly badge: string;
  readonly info: string;
  readonly label: string;
  readonly progress: number;
  readonly trackHint: string;
  readonly value: string;
}) {
  const [showInfo, setShowInfo] = useState(false);

  return (
    <Card style={styles.metricCard}>
      <View style={styles.metricHeader}>
        <View style={styles.metricTitleRow}>
          <Text style={styles.metricLabel}>{label}</Text>
          <Pressable
            accessibilityLabel={`اطلاعات ${label}`}
            accessibilityRole="button"
            onPress={() => setShowInfo((visible) => !visible)}
            style={styles.metricInfoButton}
          >
            <AppIcon color={fiticianTokens.colors.muted} name="info" size={15} />
          </Pressable>
        </View>
        {badge ? <Text style={styles.metricBadge}>{badge}</Text> : null}
      </View>
      <Text style={styles.metricValue}>{value}</Text>
      {showInfo ? <Text style={styles.metricInfoText}>{info}</Text> : null}
      <ProgressBar label={`پیشرفت ${label}`} progress={progress} />
      <Text style={styles.metricNote}>{trackHint}</Text>
    </Card>
  );
}

function IndicatorCard({ indicator }: { readonly indicator: BodyIndicatorPresentation }) {
  const color = toneColors[indicator.tone];
  return (
    <Card style={[styles.indicatorCard, { borderColor: `${color}42` }]}>
      <View style={styles.indicatorHeading}>
      <View style={styles.indicatorCopy}>
          <Text style={styles.indicatorTitle}>{indicator.title}</Text>
          {indicator.caption ? <Text style={styles.indicatorCaption}>{indicator.caption}</Text> : null}
          <Text style={styles.indicatorSubtitle}>{indicator.subtitle}</Text>
        </View>
        <View style={[styles.indicatorIconTile, { backgroundColor: `${color}1A` }]}>
          <AppIcon color={color} name={indicator.icon} size={18} />
        </View>
      </View>
      <View style={styles.indicatorDetail}>
        <MetricRing
          color={color}
          label={`امتیاز ${indicator.title}`}
          progress={(indicator.score ?? 0) / 100}
          size={76}
          strokeWidth={6}
          showLabel={false}
          valueLabel={indicator.score === null ? "—" : `${Math.round(indicator.score)}٪`}
        />
      </View>
    </Card>
  );
}

function formatMetric(value: number): string {
  return new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 1 }).format(value);
}

const styles = StyleSheet.create({
  body: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 23,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  bodyImage: {
    height: "100%",
    width: "100%",
  },
  cardHeading: {
    alignItems: "center",
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
  },
  cardTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    lineHeight: 24,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  captureBadge: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
  },
  captureDot: {
    backgroundColor: fiticianTokens.colors.aqua,
    borderRadius: fiticianTokens.radii.pill,
    height: 6,
    width: 6,
  },
  captureText: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "center",
    writingDirection: "rtl",
  },
  container: {
    gap: fiticianTokens.spacing[4],
  },
  headingCopy: {
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  heroCard: {
    gap: fiticianTokens.spacing[4],
    overflow: "hidden",
    padding: fiticianTokens.spacing[4],
  },
  heroCopy: {
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  heroEyebrow: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.displayEnglish,
    fontSize: 10,
    letterSpacing: 1.4,
    textAlign: "right",
  },
  heroHeader: {
    alignItems: "flex-start",
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
  },
  heroTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 30,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  iconTile: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    height: 44,
    justifyContent: "center",
    width: 44,
  },
  impressionCard: {
    gap: fiticianTokens.spacing[3],
  },
  indicatorDetail: {
    alignItems: "flex-start",
  },
  indicatorCaption: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 11,
    lineHeight: 18,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  indicatorSubtitle: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 11,
    lineHeight: 18,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  indicatorCard: {
    gap: fiticianTokens.spacing[3],
    padding: fiticianTokens.spacing[3],
  },
  indicatorCopy: {
    flex: 1,
    gap: 2,
  },
  indicatorGrid: {
    gap: fiticianTokens.spacing[3],
  },
  indicatorHeading: {
    alignItems: "center",
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
  },
  indicatorIconTile: {
    alignItems: "center",
    borderRadius: fiticianTokens.radii.small,
    height: 36,
    justifyContent: "center",
    width: 36,
  },
  indicatorScore: {
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.lg,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    textAlign: "center",
    writingDirection: "ltr",
  },
  indicatorSection: {
    gap: fiticianTokens.spacing[3],
  },
  indicatorTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  mediaFrame: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.canvas,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.large,
    borderWidth: 1,
    height: 330,
    justifyContent: "center",
    overflow: "hidden",
    position: "relative",
  },
  mediaGlow: {
    backgroundColor: "rgba(80,223,206,0.06)",
    borderRadius: 180,
    height: 280,
    position: "absolute",
    width: 180,
  },
  mediaTag: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.scrim,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    bottom: fiticianTokens.spacing[3],
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
    position: "absolute",
    right: fiticianTokens.spacing[3],
  },
  mediaTagText: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "center",
    writingDirection: "rtl",
  },
  metricCard: {
    gap: fiticianTokens.spacing[3],
    minWidth: 0,
    padding: fiticianTokens.spacing[3],
  },
  metricHeader: {
    alignItems: "center",
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
    justifyContent: "space-between",
  },
  metricGrid: {
    flexDirection: "column",
    gap: fiticianTokens.spacing[3],
  },
  metricInfoButton: {
    alignItems: "center",
    justifyContent: "center",
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    minWidth: fiticianTokens.layout.minimumTouchTarget,
  },
  metricInfoText: {
    backgroundColor: fiticianTokens.colors.canvas,
    borderRadius: fiticianTokens.radii.small,
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 20,
    padding: fiticianTokens.spacing[2],
    textAlign: "auto",
    writingDirection: "rtl",
  },
  metricLabel: {
    color: fiticianTokens.colors.muted,
    flex: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 11,
    lineHeight: 18,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  metricBadge: {
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 10,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    paddingHorizontal: fiticianTokens.spacing[2],
    paddingVertical: fiticianTokens.spacing[1],
    textAlign: "center",
    writingDirection: "rtl",
  },
  metricTitleRow: {
    alignItems: "center",
    flex: 1,
    flexDirection: "row",
    gap: fiticianTokens.spacing[1],
  },
  metricNote: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 11,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  metricValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.metric,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    textAlign: "right",
    writingDirection: "ltr",
  },
  route: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 23,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  viewTab: {
    alignItems: "center",
    borderRadius: fiticianTokens.radii.medium,
    flex: 1,
    flexDirection: "row",
    gap: fiticianTokens.spacing[1],
    justifyContent: "center",
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: fiticianTokens.spacing[2],
  },
  viewTabActive: {
    backgroundColor: fiticianTokens.colors.aqua,
  },
  viewTabPressed: {
    opacity: 0.82,
    transform: [{ scale: fiticianTokens.motion.pressedScale }],
  },
  viewTabText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "center",
    writingDirection: "rtl",
  },
  viewTabTextActive: {
    color: fiticianTokens.colors.canvas,
  },
  viewTabs: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderRadius: fiticianTokens.radii.medium,
    flexDirection: "row",
    gap: fiticianTokens.spacing[1],
    padding: fiticianTokens.spacing[1],
  },
});
