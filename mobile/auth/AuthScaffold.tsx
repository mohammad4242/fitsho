import { type ReactNode } from "react";
import { Text, View } from "react-native";

import { PageHeading } from "../ui/components";
import { Screen } from "../ui/layout";
import { authCopy } from "./copy";
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
          <Text style={authStyles.brand}>{authCopy.common.brand}</Text>
        </View>
        <PageHeading
          compact={false}
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
