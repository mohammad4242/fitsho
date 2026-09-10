import { useMemo, useState } from "react";
import { Image, Pressable, StyleSheet, Text, View } from "react-native";

import type {
  BodyAnalysisExperienceRegion,
  BodyAnalysisExperienceV4,
  BodyPhotoView,
} from "@fitician/core/body-photos";

import {
  AppIcon,
  Card,
  SectionHeader,
  SegmentedControl,
} from "../ui/components";
import { fiticianTokens } from "../ui/tokens";
import { bodyAssets } from "./bodyAnalysisAssets";
import {
  bodyAreaLabel,
  bodyRegionClassificationLabel,
  bodyRegionInsight,
} from "./bodyAnalysisPresentation";

type MapView = Extract<BodyPhotoView, "front" | "back">;

const mapViews: readonly { label: string; value: MapView }[] = [
  { label: "نمای روبه‌رو", value: "front" },
  { label: "نمای پشت", value: "back" },
];

const viewLabels: Record<MapView, string> = {
  back: "پشت",
  front: "روبه‌رو",
};

const allViewLabels: Record<BodyPhotoView, string> = {
  back: "پشت",
  front: "روبه‌رو",
  side: "نیمرخ",
};

export function BodyAnalysisMuscleSection({
  experience,
}: {
  readonly experience: BodyAnalysisExperienceV4;
}) {
  const [activeView, setActiveView] = useState<MapView>("front");
  const [selectedArea, setSelectedArea] = useState<string | null>(null);
  const sex = experience.input_snapshot.sex === "female" ? "female" : "male";
  const visibleRegions = useMemo(
    () => experience.regions.filter((region) => region.supporting_views.includes(activeView)),
    [activeView, experience.regions],
  );
  const selectedRegion = experience.regions.find((region) => region.area === selectedArea);

  function changeView(value: string) {
    if (value !== "front" && value !== "back") return;
    setActiveView(value);
    setSelectedArea(null);
  }

  return (
    <View style={styles.container}>
      <SectionHeader eyebrow="نقشهٔ بدن" title="یافته‌های همین تحلیل" />
      <Text style={styles.intro}>برای دیدن یک ناحیه، روی نام آن بزن.</Text>

      <Card variant="hero" style={styles.mapCard}>
        <View style={styles.mapHeader}>
          <View style={styles.mapCopy}>
            <Text style={styles.mapEyebrow}>BODY MAP</Text>
            <Text style={styles.mapTitle}>روی هر ناحیه بزن تا جزئیاتش رو ببینی</Text>
          </View>
          <View style={styles.viewBadge}>
            <Text style={styles.viewBadgeText}>{viewLabels[activeView]}</Text>
            <AppIcon color={fiticianTokens.colors.aqua} name="bodyAnalysis" size={16} />
          </View>
        </View>
        <View style={styles.figureFrame}>
          <View style={styles.figureGlow} />
          <Image
            accessibilityLabel={`تصویر بدن از ${viewLabels[activeView]}`}
            resizeMode="contain"
            source={bodyAssets[sex][activeView]}
            style={styles.figure}
          />
        </View>
      </Card>

      <SegmentedControl
        accessibilityLabel="نمای نقشهٔ بدن"
        onChange={changeView}
        options={mapViews}
        selectedValue={activeView}
        testID="body-analysis-map-views"
      />

      <View accessibilityRole="list" style={styles.regionList}>
        {visibleRegions.length === 0 ? (
          <Card style={styles.emptyCard}>
            <Text style={styles.body}>برای این نما، ناحیهٔ قابل ارزیابی ثبت نشده است.</Text>
          </Card>
        ) : visibleRegions.map((region) => (
          <RegionButton
            key={region.area}
            onPress={() => setSelectedArea(region.area)}
            region={region}
            selected={selectedArea === region.area}
          />
        ))}
      </View>

      {selectedRegion !== undefined ? (
        <Card accessibilityLiveRegion="polite" style={styles.selectionCard} variant="glass">
          <Text style={styles.selectionEyebrow}>ناحیهٔ انتخاب‌شده</Text>
          <Text style={styles.selectionTitle}>{bodyAreaLabel(selectedRegion.area)}</Text>
          <Text style={styles.body}>{bodyRegionInsight(selectedRegion)}</Text>
          <Text style={styles.muted}>
            نماهای پشتیبان: {selectedRegion.supporting_views.map((view) => allViewLabels[view]).join("، ")}
          </Text>
        </Card>
      ) : null}

      <View style={styles.summaryStack}>
        <RegionSummaryCard
          emptyText="فعلاً نقطه‌ضعف واضحی ثبت نشده."
          regions={experience.regions.filter((region) => (
            region.display_classification === "primary_priority"
            || region.display_classification === "room_to_grow"
          ))}
          title="نقاط نیازمند تمرکز"
        />
        <RegionSummaryCard
          emptyText="فعلاً نقطه‌قوت مشخصی ثبت نشده."
          regions={experience.regions.filter((region) => region.display_classification === "stronger")}
          title="نقاط قوت مهم"
        />
      </View>
    </View>
  );
}

function RegionButton({
  onPress,
  region,
  selected,
}: {
  readonly onPress: () => void;
  readonly region: BodyAnalysisExperienceRegion;
  readonly selected: boolean;
}) {
  return (
    <Pressable
      accessibilityLabel={bodyAreaLabel(region.area)}
      accessibilityRole="button"
      accessibilityState={{ selected }}
      onPress={onPress}
      style={({ pressed }) => [styles.regionButton, selected && styles.regionButtonSelected, pressed && styles.pressed]}
    >
      <View style={styles.regionDot} />
      <View style={styles.regionCopy}>
        <Text style={styles.regionTitle}>{bodyAreaLabel(region.area)}</Text>
        <Text style={styles.regionStatus}>{bodyRegionClassificationLabel(region.display_classification)}</Text>
      </View>
      <AppIcon color={selected ? fiticianTokens.colors.aqua : fiticianTokens.colors.muted} name="arrowLeft" size={20} />
    </Pressable>
  );
}

function RegionSummaryCard({
  emptyText,
  regions,
  title,
}: {
  readonly emptyText: string;
  readonly regions: readonly BodyAnalysisExperienceRegion[];
  readonly title: string;
}) {
  return (
    <Card style={styles.summaryCard}>
      <Text style={styles.summaryTitle}>{title}</Text>
      {regions.length === 0 ? (
        <Text style={styles.body}>{emptyText}</Text>
      ) : (
        <View style={styles.summaryChips}>
          {regions.slice(0, 3).map((region) => (
            <View key={region.area} style={styles.summaryChip}>
              <Text style={styles.summaryChipText}>{bodyAreaLabel(region.area)}</Text>
              <View style={styles.summaryDot} />
            </View>
          ))}
        </View>
      )}
    </Card>
  );
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
  container: {
    gap: fiticianTokens.spacing[3],
  },
  emptyCard: {
    padding: fiticianTokens.spacing[3],
  },
  figure: {
    height: "100%",
    width: "100%",
  },
  figureFrame: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.canvas,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.large,
    borderWidth: 1,
    height: 280,
    justifyContent: "center",
    overflow: "hidden",
    position: "relative",
  },
  figureGlow: {
    backgroundColor: "rgba(80,223,206,0.06)",
    borderRadius: 180,
    height: 250,
    position: "absolute",
    width: 170,
  },
  intro: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 22,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  mapCard: {
    gap: fiticianTokens.spacing[3],
    padding: fiticianTokens.spacing[3],
  },
  mapCopy: {
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  mapEyebrow: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.displayEnglish,
    fontSize: 10,
    letterSpacing: 1.4,
    textAlign: "right",
  },
  mapHeader: {
    alignItems: "flex-start",
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
    justifyContent: "space-between",
  },
  mapTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 28,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  muted: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 20,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  pressed: {
    opacity: 0.82,
    transform: [{ scale: fiticianTokens.motion.pressedScale }],
  },
  regionButton: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surface,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
  },
  regionButtonSelected: {
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.aqua,
  },
  regionCopy: {
    flex: 1,
    gap: 2,
  },
  regionDot: {
    backgroundColor: fiticianTokens.colors.aqua,
    borderRadius: fiticianTokens.radii.pill,
    height: 8,
    width: 8,
  },
  regionList: {
    gap: fiticianTokens.spacing[2],
  },
  regionStatus: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  regionTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  selectionCard: {
    gap: fiticianTokens.spacing[2],
  },
  selectionEyebrow: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  selectionTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 28,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  summaryCard: {
    gap: fiticianTokens.spacing[2],
    padding: fiticianTokens.spacing[3],
  },
  summaryChips: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
  summaryTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  summaryChip: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    flexDirection: "row",
    gap: fiticianTokens.spacing[1],
    paddingHorizontal: fiticianTokens.spacing[2],
    paddingVertical: fiticianTokens.spacing[1],
  },
  summaryChipText: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "center",
    writingDirection: "rtl",
  },
  summaryDot: {
    backgroundColor: fiticianTokens.colors.aqua,
    borderRadius: fiticianTokens.radii.pill,
    height: 6,
    width: 6,
  },
  summaryStack: {
    gap: fiticianTokens.spacing[2],
  },
  viewBadge: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    flexDirection: "row",
    gap: fiticianTokens.spacing[1],
    paddingHorizontal: fiticianTokens.spacing[2],
    paddingVertical: fiticianTokens.spacing[1],
  },
  viewBadgeText: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "center",
    writingDirection: "rtl",
  },
});
