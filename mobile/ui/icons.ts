import type { ComponentProps } from "react";
import { MaterialCommunityIcons } from "@expo/vector-icons";

export const fiticianIconNames = [
  "home",
  "training",
  "nutrition",
  "profile",
  "more",
  "bodyAnalysis",
  "foodLog",
  "play",
  "clock",
  "calendar",
  "flame",
  "ruler",
  "scale",
  "target",
  "shield",
  "arrowLeft",
  "chevronDown",
  "chevronUp",
  "refresh",
  "close",
  "genderMale",
  "genderFemale",
] as const;

export type FiticianIconName = (typeof fiticianIconNames)[number];
export type MaterialIconName = ComponentProps<typeof MaterialCommunityIcons>["name"];

const iconMap: Record<FiticianIconName, MaterialIconName> = {
  home: "home-variant-outline",
  training: "dumbbell",
  nutrition: "silverware-fork-knife",
  profile: "account-circle-outline",
  more: "dots-horizontal",
  bodyAnalysis: "human-male-height-variant",
  foodLog: "food-apple-outline",
  play: "play-circle-outline",
  clock: "clock-outline",
  calendar: "calendar-outline",
  flame: "fire",
  ruler: "ruler",
  scale: "scale-balance",
  target: "target",
  shield: "shield-check-outline",
  arrowLeft: "arrow-left",
  chevronDown: "chevron-down",
  chevronUp: "chevron-up",
  refresh: "refresh",
  close: "close",
  genderMale: "gender-male",
  genderFemale: "gender-female",
};

export function fiticianIconName(name: FiticianIconName): MaterialIconName {
  return iconMap[name];
}
