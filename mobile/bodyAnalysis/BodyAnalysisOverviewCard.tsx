import { useState } from "react";
import {
  Image,
  Pressable,
  StyleSheet,
  Text,
  View,
  type ImageSourcePropType,
} from "react-native";

import type { BodyAnalysisExperienceV4, BodyPhotoView } from "@fitician/core/body-photos";

import { AppIcon, Card, ProgressBar, SectionHeader } from "../ui/components";
import type { FiticianIconName } from "../ui/icons";
import { fiticianTokens } from "../ui/tokens";
import {
  bodyBmiLabel,
  bodyMetricProgress,
  buildBodyIndicatorSummary,
  type BodyIndicatorPresentation,
  type BodyIndicatorTone,
} from "./bodyAnalysisPresentation";

type BodyAssetSet = Record<BodyPhotoView, ImageSourcePropType>;

const bodyAssets: Record<"female" | "male", BodyAssetSet> = {
  female: {
    back: require("../assets/body-analysis/female-back.jpg"),
    front: require("../assets/body-analysis/female-front.jpg"),
    side: require("../assets/body-analysis/female-side.jpg"),
  },
  male: {
    back: require("../assets/body-analysis/male-back.jpg"),
    front: require("../assets/body-analysis/male-front.jpg"),
    side: require("../assets/body-analysis/male-side.jpg"),
  },
};

const viewLabels: Record<BodyPhotoView, string> = {
  back: "پشت",
  front: "روبه‌رو",
  side: "نیمرخ",
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
  const bodyFat = experience.body_composition.estimated_body_fat_percent;
  const bmi = experience.body_composition.bmi;
  const indicators = buildBodyIndicatorSummary(experience);

  return (
    <View style={styles.container}>
      <SectionHeader eyebrow="اسکن و شاخص‌ها" title="تصویر کلی بدن" />
      <Card variant="hero" style={styles.heroCard}>
        <View style={styles.heroHeader}>
          <View style={styles.captureBadge}>
            <View style={styles.captureDot} />
            <Text style={styles.captureText}>۳ نمای استاندارد</Text>
          </View>
          <View style={styles.heroCopy}>
            <Text style={styles.heroEyebrow}>BODY SCAN</Text>
            <Text style={styles.heroTitle}>بدن، نقطه شروع مسیر تو</Text>
          </View>
        </View>

        <View style={styles.mediaFrame}>
          <View style={styles.mediaGlow} />
          <Image
            accessibilityLabel={`نمای ${viewLabels[activeView]} آنالیز بدن`}
            resizeMode="contain"
            source={bodyAssets[sex][activeView]}
            style={styles.bodyImage}
          />
          <View style={styles.mediaTag}>
            <AppIcon accessibilityLabel="نمای بدن" color={fiticianTokens.colors.aqua} name="bodyAnalysis" size={16} />
            <Text style={styles.mediaTagText}>{viewLabels[activeView]}</Text>
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
              <AppIcon
                color={activeView === view ? fiticianTokens.colors.canvas : fiticianTokens.colors.muted}
                name="bodyAnalysis"
                size={17}
              />
              <Text style={[styles.viewTabText, activeView === view && styles.viewTabTextActive]}>
                {viewLabels[view]}
              </Text>
            </Pressable>
          ))}
        </View>
      </Card>

      <View style={styles.metricGrid}>
        <BodyMetricCard
          icon="target"
          label="درصد چربی تخمینی"
          note="برآورد تصویری"
          progress={bodyMetricProgress(bodyFat, 10, 35)}
          value={bodyFat === null ? "—" : `${formatMetric(bodyFat)}٪`}
        />
        <BodyMetricCard
          icon="bodyAnalysis"
          label="شاخص توده بدنی"
          note={bodyBmiLabel(bmi)}
          progress={bodyMetricProgress(bmi, 15, 35)}
          value={bmi === null ? "—" : formatMetric(bmi)}
        />
      </View>

      <Card variant="glass" style={styles.impressionCard}>
        <View style={styles.cardHeading}>
          <View style={styles.iconTile}>
            <AppIcon color={fiticianTokens.colors.aqua} name="bodyAnalysis" size={20} />
          </View>
          <View style={styles.headingCopy}>
            <Text style={styles.cardEyebrow}>برداشت اولیه</Text>
            <Text style={styles.cardTitle}>{firstImpressionTitle(experience)}</Text>
          </View>
        </View>
        <Text style={styles.body}>{firstImpressionBody(experience)}</Text>
      </Card>

      <View style={styles.indicatorSection}>
        <SectionHeader eyebrow="تحلیل تصویری" title="سه شاخص کلیدی" />
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
  icon,
  label,
  note,
  progress,
  value,
}: {
  readonly icon: FiticianIconName;
  readonly label: string;
  readonly note: string;
  readonly progress: number;
  readonly value: string;
}) {
  return (
    <Card style={styles.metricCard}>
      <View style={styles.metricIconRow}>
        <View style={styles.metricIconTile}>
          <AppIcon color={fiticianTokens.colors.aqua} name={icon} size={18} />
        </View>
        <Text style={styles.metricLabel}>{label}</Text>
      </View>
      <Text style={styles.metricValue}>{value}</Text>
      <ProgressBar label={`پیشرفت ${label}`} progress={progress} />
      <Text style={styles.metricNote}>{note}</Text>
    </Card>
  );
}

function IndicatorCard({ indicator }: { readonly indicator: BodyIndicatorPresentation }) {
  const color = toneColors[indicator.tone];
  return (
    <Card style={[styles.indicatorCard, { borderColor: `${color}42` }]}>
      <View style={styles.indicatorHeading}>
        <View style={[styles.indicatorIconTile, { backgroundColor: `${color}1A` }]}>
          <AppIcon color={color} name={indicator.icon} size={18} />
        </View>
        <View style={styles.indicatorCopy}>
          <Text style={styles.indicatorTitle}>{indicator.title}</Text>
          <Text style={styles.indicatorCaption}>{indicator.caption}</Text>
        </View>
        <Text style={[styles.indicatorScore, { color }]}>
          {indicator.score === null ? "—" : `${Math.round(indicator.score)}٪`}
        </Text>
      </View>
      <ProgressBar color={color} label={`امتیاز ${indicator.title}`} progress={(indicator.score ?? 0) / 100} />
    </Card>
  );
}

function firstImpressionTitle(experience: BodyAnalysisExperienceV4): string {
  if (experience.assessment_status === "partial") return "ارزیابی اولیه هنوز کامل نیست";
  if (experience.direction.status === "goal_confirmation_required") return "یک مسیر قابل تنظیم برای تو آماده است";
  return "تصویر اولیه‌ی بدنت آماده است";
}

function firstImpressionBody(experience: BodyAnalysisExperienceV4): string {
  if (experience.assessment_status === "partial") {
    return "بعضی شاخص‌ها به دلیل کیفیت یا محدودیت نماها قابل ارزیابی نیستند.";
  }
  if (experience.direction.status === "goal_confirmation_required") {
    return "با تأیید هدف فعلی، پیشنهادهای تمرین و تغذیه دقیق‌تر با وضعیت بدنت هماهنگ می‌شوند.";
  }
  return "این خلاصه از داده‌های نشست فعلی ساخته شده و مبنای شخصی‌سازی مسیر توست.";
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
    textAlign: "right",
    writingDirection: "rtl",
  },
  bodyImage: {
    height: "100%",
    width: "100%",
  },
  cardEyebrow: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  cardHeading: {
    alignItems: "center",
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
  },
  cardTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    lineHeight: 24,
    textAlign: "right",
    writingDirection: "rtl",
  },
  captureBadge: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    flexDirection: "row-reverse",
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
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
  },
  heroTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 30,
    textAlign: "right",
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
  indicatorCaption: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 11,
    lineHeight: 18,
    textAlign: "right",
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
    flexDirection: "row-reverse",
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
  },
  indicatorSection: {
    gap: fiticianTokens.spacing[3],
  },
  indicatorTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
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
    flexDirection: "row-reverse",
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
    writingDirection: "rtl",
  },
  metricCard: {
    flex: 1,
    gap: fiticianTokens.spacing[3],
    minWidth: 0,
    padding: fiticianTokens.spacing[3],
  },
  metricGrid: {
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
  },
  metricIconRow: {
    alignItems: "center",
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[2],
  },
  metricIconTile: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderRadius: fiticianTokens.radii.small,
    height: 32,
    justifyContent: "center",
    width: 32,
  },
  metricLabel: {
    color: fiticianTokens.colors.muted,
    flex: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 11,
    lineHeight: 18,
    textAlign: "right",
    writingDirection: "rtl",
  },
  metricNote: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 11,
    textAlign: "right",
    writingDirection: "rtl",
  },
  metricValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.metric,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    textAlign: "right",
  },
  viewTab: {
    alignItems: "center",
    borderRadius: fiticianTokens.radii.medium,
    flex: 1,
    flexDirection: "row-reverse",
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
    writingDirection: "rtl",
  },
  viewTabTextActive: {
    color: fiticianTokens.colors.canvas,
  },
  viewTabs: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderRadius: fiticianTokens.radii.medium,
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[1],
    padding: fiticianTokens.spacing[1],
  },
});
