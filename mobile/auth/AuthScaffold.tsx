import { type ReactNode } from "react";
import { Text, View } from "react-native";

import { Screen } from "../ui/layout";
import { authStyles } from "./authStyles";

export interface AuthScaffoldProps {
  readonly children: ReactNode;
  readonly subtitle?: string;
  readonly title: string;
}

export function AuthScaffold({ children, subtitle, title }: AuthScaffoldProps) {
  return (
    <Screen contentContainerStyle={authStyles.content} contentWidth="reading">
      <View style={authStyles.content}>
        <Text style={authStyles.brand}>FITICIAN</Text>
        <Text accessibilityRole="header" style={authStyles.title}>{title}</Text>
        {subtitle ? <Text style={authStyles.subtitle}>{subtitle}</Text> : null}
        {children}
      </View>
    </Screen>
  );
}
