import type { ComponentProps } from "react";
import { MaterialCommunityIcons } from "@expo/vector-icons";

import type { FiticianDirection } from "./rtl";

export const fiticianIconNames = [
  "home",
  "training",
  "nutrition",
  "profile",
  "doctor",
  "supplement",
  "lab",
  "document",
  "check",
  "more",
  "bodyAnalysis",
  "camera",
  "delete",
  "foodLog",
  "play",
  "clock",
  "calendar",
  "flame",
  "flash",
  "ruler",
  "scale",
  "target",
  "shield",
  "arrowLeft",
  "arrowRight",
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
  doctor: "doctor",
  supplement: "pill",
  lab: "flask-outline",
  document: "file-document-outline",
  check: "check",
  more: "dots-horizontal",
  bodyAnalysis: "human-male-height-variant",
  camera: "camera-outline",
  delete: "delete-outline",
  foodLog: "food-apple-outline",
  play: "play-circle-outline",
  clock: "clock-outline",
  calendar: "calendar-outline",
  flame: "fire",
  flash: "flash",
  ruler: "ruler",
  scale: "scale-balance",
  target: "target",
  shield: "shield-check-outline",
  arrowLeft: "arrow-left",
  arrowRight: "arrow-right",
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

export type FiticianDirectionalIcon = "back" | "forward";

export function fiticianDirectionalIconName(
  semantic: FiticianDirectionalIcon,
  direction: FiticianDirection = "rtl",
): "arrowLeft" | "arrowRight" {
  if (semantic === "back") return direction === "rtl" ? "arrowRight" : "arrowLeft";
  return direction === "rtl" ? "arrowLeft" : "arrowRight";
}
