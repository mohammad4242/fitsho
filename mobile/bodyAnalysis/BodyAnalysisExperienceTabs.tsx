import { useState, type ReactNode } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import type {
  BodyAnalysisExperienceV4,
  BodyProgressTimelineItem,
} from "@fitician/core/body-photos";

import { AppIcon } from "../ui/components";
import { RTL_LAYOUT, RTL_ROW } from "../ui/rtl";
import { fiticianTokens } from "../ui/tokens";
import { BodyAnalysisMuscleSection } from "./BodyAnalysisMuscleSection";
import { BodyAnalysisOverviewCard } from "./BodyAnalysisOverviewCard";
import { BodyAnalysisProgressStrip } from "./BodyAnalysisProgressStrip";
import { bodyAnalysisCopy } from "./bodyAnalysisCopy";

type ResultTab = "overview" | "muscles" | "progress";

const tabs: readonly { icon: "bodyAnalysis" | "training" | "clock"; key: ResultTab; label: string }[] = [
  { icon: "bodyAnalysis", key: "overview", label: bodyAnalysisCopy.tabs.overview },
  { icon: "training", key: "muscles", label: bodyAnalysisCopy.tabs.muscles },
  { icon: "clock", key: "progress", label: bodyAnalysisCopy.tabs.progress },
];

export function BodyAnalysisExperienceTabs({
  experience,
  progressItems,
  progressSessionId,
  review,
}: {
  readonly experience: BodyAnalysisExperienceV4;
  readonly progressItems: readonly BodyProgressTimelineItem[];
  readonly progressSessionId: string;
  readonly review: ReactNode;
}) {
  const [activeTab, setActiveTab] = useState<ResultTab>("overview");
  const activeLabel = tabs.find((tab) => tab.key === activeTab)?.label ?? bodyAnalysisCopy.tabs.overview;

  return (
    <View style={styles.container}>
      <View
        accessibilityLabel="تب‌های نتیجه تحلیل بدن"
        accessibilityRole="tablist"
        style={styles.tabList}
      >
        {tabs.map((tab) => {
          const selected = tab.key === activeTab;
          return (
            <Pressable
              accessibilityLabel={tab.label}
              accessibilityRole="tab"
              accessibilityState={{ selected }}
              key={tab.key}
              onPress={() => setActiveTab(tab.key)}
              style={({ pressed }) => [
                styles.tab,
                selected && styles.tabSelected,
                pressed && styles.tabPressed,
              ]}
            >
              <AppIcon
                color={selected ? fiticianTokens.colors.ink : fiticianTokens.colors.muted}
                name={tab.icon}
                size={18}
              />
              <Text style={[styles.tabLabel, selected && styles.tabLabelSelected]}>{tab.label}</Text>
            </Pressable>
          );
        })}
      </View>

      <View accessibilityLabel={activeLabel} style={styles.panel}>
        {activeTab === "overview" ? <BodyAnalysisOverviewCard experience={experience} /> : null}
        {activeTab === "muscles" ? <BodyAnalysisMuscleSection experience={experience} /> : null}
        {activeTab === "progress" ? (
          <>
            <BodyAnalysisProgressStrip currentSessionId={progressSessionId} items={progressItems} />
            {review}
          </>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: fiticianTokens.spacing[3],
  },
  panel: {
    gap: fiticianTokens.spacing[4],
  },
  tab: {
    ...RTL_LAYOUT,
    alignItems: "center",
    backgroundColor: "transparent",
    borderColor: "transparent",
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    flex: 1,
    gap: fiticianTokens.spacing[1],
    justifyContent: "center",
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: fiticianTokens.spacing[2],
    paddingVertical: fiticianTokens.spacing[1],
  },
  tabLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "center",
    writingDirection: "rtl",
  },
  tabLabelSelected: {
    color: fiticianTokens.colors.ink,
  },
  tabList: {
    ...RTL_LAYOUT,
    ...RTL_ROW,
    alignSelf: "center",
    backgroundColor: "rgba(8,22,27,0.85)",
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    gap: fiticianTokens.spacing[1],
    maxWidth: "100%",
    padding: fiticianTokens.spacing[1],
    width: "100%",
  },
  tabPressed: {
    opacity: 0.82,
    transform: [{ scale: fiticianTokens.motion.pressedScale }],
  },
  tabSelected: {
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.aqua,
    shadowColor: fiticianTokens.colors.aqua,
    shadowOpacity: 0.25,
    shadowRadius: 8,
  },
});
