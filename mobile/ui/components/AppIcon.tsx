import { MaterialCommunityIcons } from "@expo/vector-icons";
import type { ComponentProps } from "react";
import { type ColorValue, type StyleProp, type TextStyle } from "react-native";

import { fiticianIconName, type FiticianIconName } from "../icons";
import { fiticianTokens } from "../tokens";

export interface AppIconProps {
  readonly accessibilityLabel?: string;
  readonly color?: ColorValue;
  readonly name: FiticianIconName;
  readonly size?: number;
  readonly style?: StyleProp<TextStyle>;
}

export function AppIcon({ accessibilityLabel, color, name, size = fiticianTokens.iconSize.md, style }: AppIconProps) {
  const props: ComponentProps<typeof MaterialCommunityIcons> = {
    accessibilityLabel,
    color: color ?? fiticianTokens.colors.ink,
    name: fiticianIconName(name),
    size,
    style,
  };
  return <MaterialCommunityIcons {...props} accessible={accessibilityLabel !== undefined} />;
}
