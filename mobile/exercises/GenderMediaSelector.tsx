import { Pressable, StyleSheet, View } from "react-native";

import { AppIcon } from "../ui/components/AppIcon";
import { fiticianTokens } from "../ui/tokens";
import type { MobileLanguage } from "../ui/rtl";
import type { GenderMediaPresentation } from "./exerciseMedia";

export interface GenderMediaSelectorProps {
  readonly available: readonly GenderMediaPresentation[];
  readonly language: MobileLanguage;
  readonly onChange: (presentation: GenderMediaPresentation) => void;
  readonly selected: GenderMediaPresentation;
}

const labels: Record<MobileLanguage, Record<GenderMediaPresentation, string>> = {
  en: {
    female: "Female video",
    male: "Male video",
  },
  fa: {
    female: "ویدیوی زن",
    male: "ویدیوی مرد",
  },
};

const icons: Record<GenderMediaPresentation, "genderMale" | "genderFemale"> = {
  female: "genderFemale",
  male: "genderMale",
};

export function GenderMediaSelector({
  available,
  language,
  onChange,
  selected,
}: GenderMediaSelectorProps) {
  if (available.length === 0) return null;

  return (
    <View
      style={[styles.container, language === "fa" ? styles.rtl : styles.ltr]}
      testID="exercise-media-gender-selector"
    >
      {available.map((presentation) => {
        const isSelected = presentation === selected;
        return (
          <Pressable
            accessible
            accessibilityLabel={labels[language][presentation]}
            accessibilityHint={language === "en" ? "Change exercise video" : "تغییر ویدیوی حرکت"}
            accessibilityRole="radio"
            accessibilityState={{ selected: isSelected }}
            hitSlop={6}
            key={presentation}
            onPress={() => onChange(presentation)}
            style={({ pressed }) => [
              styles.option,
              isSelected && styles.optionSelected,
              pressed && styles.optionPressed,
            ]}
            testID={`exercise-media-gender-${presentation}`}
          >
            <AppIcon
              color={isSelected ? fiticianTokens.colors.canvas : fiticianTokens.colors.muted}
              name={icons[presentation]}
              size={19}
            />
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: "center",
    gap: fiticianTokens.spacing[2],
    justifyContent: "center",
    width: "100%",
  },
  ltr: {
    flexDirection: "row",
  },
  option: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    height: fiticianTokens.layout.minimumTouchTarget,
    justifyContent: "center",
    width: fiticianTokens.layout.minimumTouchTarget,
  },
  optionPressed: {
    opacity: 0.76,
  },
  optionSelected: {
    backgroundColor: fiticianTokens.colors.aqua,
    borderColor: fiticianTokens.colors.aqua,
  },
  rtl: {
    flexDirection: "row",
  },
});
