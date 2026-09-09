import { type ReactNode } from "react";
import { Text, View } from "react-native";

import { AppIcon, PageHeading } from "../ui/components";
import { Screen } from "../ui/layout";
import { authStyles } from "./authStyles";

export interface AuthScaffoldProps {
  readonly children: ReactNode;
  readonly eyebrow?: string;
  readonly subtitle?: string;
  readonly title: string;
}

export function AuthScaffold({ children, eyebrow, subtitle, title }: AuthScaffoldProps) {
  return (
    <Screen contentContainerStyle={authStyles.screen} contentWidth="reading">
      <View style={authStyles.panel} testID="auth-form-panel">
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
        <PageHeading
          eyebrow={eyebrow}
          style={authStyles.heading}
          supportingText={subtitle}
          title={title}
        />
        {children}
      </View>
    </Screen>
  );
}

export function AuthFormSection({ children }: { readonly children: ReactNode }) {
  return <View style={authStyles.formSection}>{children}</View>;
}
