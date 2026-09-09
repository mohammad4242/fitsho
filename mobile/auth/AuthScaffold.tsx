import { type ReactNode } from "react";
import { Text, View } from "react-native";

import { AppIcon, Card } from "../ui/components";
import { Screen } from "../ui/layout";
import { authStyles } from "./authStyles";

export interface AuthScaffoldProps {
  readonly children: ReactNode;
  readonly subtitle?: string;
  readonly title: string;
}

export function AuthScaffold({ children, subtitle, title }: AuthScaffoldProps) {
  return (
    <Screen contentContainerStyle={authStyles.screen} contentWidth="reading">
      <View style={authStyles.content}>
        <View style={authStyles.brandRow}>
          <View style={authStyles.brandLockup}>
            <View style={authStyles.brandMark}>
              <AppIcon color={authStyles.brandIcon.color} name="shield" size={16} />
            </View>
            <Text style={authStyles.brand}>FITICIAN</Text>
          </View>
          <Text style={authStyles.productTag}>مربی شخصی دیجیتال</Text>
        </View>
        <View style={authStyles.accentRule}>
          <View style={authStyles.accentRuleFill} />
        </View>
        <Text accessibilityRole="header" style={authStyles.title}>{title}</Text>
        {subtitle ? <Text style={authStyles.subtitle}>{subtitle}</Text> : null}
        {children}
      </View>
    </Screen>
  );
}

export function AuthFormCard({ children }: { readonly children: ReactNode }) {
  return <Card variant="glass" style={authStyles.formCard}>{children}</Card>;
}
