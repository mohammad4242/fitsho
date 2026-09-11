import { useMemo, useState } from "react";
import { Image, StyleSheet, Text, View } from "react-native";
import {
  Defs,
  Mask,
  Path,
  Rect,
  Svg,
} from "react-native-svg";

import type { BodyAnalysisExperienceRegion, BodyAnalysisExperienceV4 } from "@fitician/core/body-photos";
import {
  bodyMapHitRegions,
  bodyMapRegions,
  bodyMapSex,
  bodyMapVisualMask,
  type BodyMapSex,
  type BodyMapView,
} from "./bodyAnalysisMap";

import {
  AppIcon,
  Card,
  SectionHeader,
  SegmentedControl,
} from "../ui/components";
import { fiticianTokens } from "../ui/tokens";
import { bodyResultAssets } from "./bodyAnalysisAssets";
import {
  bodyAreaLabel,
  bodyRegionClassificationLabel,
  bodyRegionInsight,
} from "./bodyAnalysisPresentation";

const BODY_MAP_HEIGHT = 1280;
const BODY_MAP_VIEWBOX = "0 0 853 1280";
const BODY_MAP_WIDTH = 853;
const BODY_MAP_AQUA = "#50DFCE";

const mapViews: readonly { label: string; value: BodyMapView }[] = [
  { label: "نمای روبه‌رو", value: "front" },
  { label: "نمای پشت", value: "back" },
];

const viewLabels: Record<BodyMapView, string> = {
  back: "پشت",
  front: "روبه‌رو",
};

const sexLabels: Record<BodyMapSex, string> = {
  female: "زن",
  male: "مرد",
  neutral: "خنثی",
};

const allViewLabels: Record<"back" | "front" | "side", string> = {
  back: "پشت",
  front: "روبه‌رو",
  side: "نیمرخ",
};

export function BodyAnalysisMuscleSection({
  experience,
}: {
  readonly experience: BodyAnalysisExperienceV4;
}) {
  const [activeView, setActiveView] = useState<BodyMapView>("front");
  const [selectedArea, setSelectedArea] = useState<BodyAnalysisExperienceRegion["area"] | null>(null);
  const sex = bodyMapSex(experience.input_snapshot.sex);
  const assetSex = sex === "female" ? "female" : "male";
  const regionsByArea = useMemo(
    () => new Map(experience.regions.map((region) => [region.area, region] as const)),
    [experience.regions],
  );
  const layoutsByArea = useMemo(
    () => new Map(bodyMapRegions.map((layout) => [layout.area, layout] as const)),
    [],
  );
  const hitRegions = useMemo(
    () => bodyMapHitRegions(sex, activeView).filter((hitRegion) => {
      const layout = layoutsByArea.get(hitRegion.area);
      return layout !== undefined
        && layout.availableViews.includes(activeView)
        && regionsByArea.has(hitRegion.area);
    }),
    [activeView, layoutsByArea, regionsByArea, sex],
  );
  const selectedRegion = selectedArea === null ? undefined : regionsByArea.get(selectedArea);
  const selectedVisualMask = selectedArea === null
    ? undefined
    : bodyMapVisualMask(sex, activeView, selectedArea);
  const selectedVisualMaskId = selectedArea === null
    ? undefined
    : `body-analysis-map-mask-${sex}-${activeView}-${selectedArea}`;

  function changeView(value: string) {
    if (value !== "front" && value !== "back") return;
    setActiveView(value);
    setSelectedArea(null);
  }

  function selectArea(area: BodyAnalysisExperienceRegion["area"]) {
    setSelectedArea(area);
  }

  const mapImageLabel = `نمای ${viewLabels[activeView]} نقشه بدن ${sexLabels[sex]}`;

  return (
    <View style={styles.container} testID="body-analysis-muscle-section">
      <SectionHeader eyebrow="نقشهٔ بدن" title="یافته‌های همین تحلیل" />
      <Text style={styles.intro}>برای دیدن یک ناحیه، روی خود بدن بزن.</Text>

      {selectedRegion !== undefined ? (
        <Card
          accessibilityLiveRegion="polite"
          style={styles.selectionCard}
          testID="body-analysis-selected-detail"
          variant="glass"
        >
          <Text style={styles.selectionEyebrow}>ناحیهٔ انتخاب‌شده</Text>
          <Text style={styles.selectionTitle}>{bodyAreaLabel(selectedRegion.area)}</Text>
          <Text style={styles.selectionStatus}>
            {bodyRegionClassificationLabel(selectedRegion.display_classification)}
          </Text>
          <Text style={styles.body}>{bodyRegionInsight(selectedRegion)}</Text>
          <Text style={styles.muted}>
            نماهای پشتیبان: {selectedRegion.supporting_views.map((view) => allViewLabels[view]).join("، ")}
          </Text>
        </Card>
      ) : null}

      <Card
        style={styles.mapCard}
        testID="body-analysis-map-card"
        variant="hero"
      >
        <View style={styles.mapHeader}>
          <View style={styles.mapCopy}>
            <Text style={styles.mapEyebrow}>BODY MAP</Text>
            <Text style={styles.mapTitle}>روی هر ناحیه بزن تا جزئیاتش رو ببینی</Text>
          </View>
          <View style={styles.sexBadge}>
            <Text style={styles.viewBadgeText}>{sexLabels[sex]}</Text>
            <AppIcon color={BODY_MAP_AQUA} name="bodyAnalysis" size={16} />
          </View>
        </View>

        <SegmentedControl
          accessibilityLabel="نمای نقشهٔ بدن"
          onChange={changeView}
          options={mapViews}
          selectedValue={activeView}
          testID="body-analysis-map-views"
        />

        <View style={styles.figureFrame}>
          <View style={styles.figureGlow} />
          <Image
            accessibilityLabel={mapImageLabel}
            resizeMode="stretch"
            source={bodyResultAssets.map[assetSex][activeView]}
            style={styles.figure}
            testID="body-analysis-map-image"
          />

          {selectedVisualMask !== undefined && selectedVisualMaskId !== undefined ? (
            <Svg
              pointerEvents="none"
              preserveAspectRatio="none"
              style={styles.mapLayer}
              testID={`body-analysis-map-mask-${selectedArea}`}
              viewBox={BODY_MAP_VIEWBOX}
            >
              <Defs>
                <Mask
                  id={selectedVisualMaskId}
                  maskContentUnits="userSpaceOnUse"
                  maskUnits="userSpaceOnUse"
                  x={0}
                  y={0}
                  width={BODY_MAP_WIDTH}
                  height={BODY_MAP_HEIGHT}
                >
                  <Rect fill="black" height={BODY_MAP_HEIGHT} width={BODY_MAP_WIDTH} x={0} y={0} />
                  {selectedVisualMask.paths.map((path, index) => (
                    <Path
                      d={path.d}
                      fill="white"
                      key={`${selectedVisualMask.file}-${index}`}
                      transform={path.transform}
                    />
                  ))}
                </Mask>
              </Defs>
              <Rect
                fill={BODY_MAP_AQUA}
                fillOpacity={0.78}
                height={BODY_MAP_HEIGHT}
                mask={`url(#${selectedVisualMaskId})`}
                width={BODY_MAP_WIDTH}
                x={0}
                y={0}
              />
            </Svg>
          ) : null}

          <Svg
            accessibilityLabel={`ناحیه‌های تعاملی ${mapImageLabel}`}
            pointerEvents="box-none"
            preserveAspectRatio="none"
            style={styles.mapLayer}
            viewBox={BODY_MAP_VIEWBOX}
          >
            {hitRegions.map((hitRegion) => {
              const region = regionsByArea.get(hitRegion.area);
              if (region === undefined) return null;
              const selected = selectedArea === hitRegion.area;
              return (
                <Path
                  accessibilityLabel={`${bodyAreaLabel(region.area)} — ${bodyRegionClassificationLabel(region.display_classification)}`}
                  d={hitRegion.d}
                  fill={BODY_MAP_AQUA}
                  fillOpacity={selected ? 0.04 : 0.01}
                  id={hitRegion.id}
                  key={hitRegion.id}
                  onPress={() => selectArea(region.area)}
                  testID={`body-analysis-map-hit-region-${region.area}`}
                />
              );
            })}
          </Svg>
        </View>
      </Card>

      <View style={styles.summaryStack}>
        <RegionSummaryCard
          emptyText="فعلاً نقطه‌ضعف واضحی ثبت نشده."
          regions={[
            ...experience.regions.filter((region) => region.display_classification === "primary_priority"),
            ...experience.regions.filter((region) => region.display_classification === "room_to_grow"),
          ].slice(0, 3)}
          title="نقاط نیازمند تمرکز"
        />
        <RegionSummaryCard
          emptyText="فعلاً نقطه‌قوت مشخصی ثبت نشده."
          regions={experience.regions.filter((region) => region.display_classification === "stronger").slice(0, 3)}
          title="نقاط قوت مهم"
        />
      </View>
    </View>
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
          {regions.map((region) => (
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
  figure: {
    height: "100%",
    position: "absolute",
    width: "100%",
  },
  figureFrame: {
    alignSelf: "center",
    backgroundColor: fiticianTokens.colors.canvas,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.large,
    borderWidth: 1,
    overflow: "hidden",
    position: "relative",
    width: "100%",
    aspectRatio: BODY_MAP_WIDTH / BODY_MAP_HEIGHT,
  },
  figureGlow: {
    backgroundColor: "rgba(80,223,206,0.12)",
    borderRadius: 180,
    height: 300,
    left: "20%",
    position: "absolute",
    top: "30%",
    width: "60%",
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
    overflow: "hidden",
    padding: fiticianTokens.spacing[3],
  },
  mapCopy: {
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  mapEyebrow: {
    color: fiticianTokens.colors.aqua,
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
  mapLayer: {
    height: "100%",
    left: 0,
    position: "absolute",
    top: 0,
    width: "100%",
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
  selectionCard: {
    borderRightColor: BODY_MAP_AQUA,
    borderRightWidth: 4,
    gap: fiticianTokens.spacing[2],
  },
  selectionEyebrow: {
    color: BODY_MAP_AQUA,
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
  selectionStatus: {
    color: BODY_MAP_AQUA,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  sexBadge: {
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
    color: BODY_MAP_AQUA,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "center",
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
  summaryDot: {
    backgroundColor: BODY_MAP_AQUA,
    borderRadius: fiticianTokens.radii.pill,
    height: 6,
    width: 6,
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
  summaryTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  summaryStack: {
    gap: fiticianTokens.spacing[2],
  },
});
