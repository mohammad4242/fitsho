import { type ReactNode } from "react";
import {
  StyleSheet,
  Text,
  TextInput,
  View,
  type StyleProp,
  type TextInputProps,
  type TextStyle,
  type ViewStyle,
} from "react-native";

import { RTL_LAYOUT, RTL_TEXT, getTextDirectionStyle } from "../rtl";
import { fiticianTokens } from "../tokens";

export interface FormFieldProps {
  readonly children: ReactNode;
  readonly description?: string;
  readonly error?: string;
  readonly label?: string;
  readonly required?: boolean;
  readonly style?: StyleProp<ViewStyle>;
}

export function FormField({
  children,
  description,
  error,
  label,
  required = false,
  style,
}: FormFieldProps) {
  const statusMessage = error ?? description;

  return (
    <View style={[styles.field, RTL_LAYOUT, style]}>
      {label ? (
        <Text style={styles.label}>
          {label}
          {required ? <Text style={styles.required}> *</Text> : null}
        </Text>
      ) : null}
      {children}
      {statusMessage ? (
        <Text style={[styles.status, error ? styles.error : styles.description]}>{statusMessage}</Text>
      ) : null}
    </View>
  );
}

export interface TextFieldProps extends Omit<TextInputProps, "accessibilityLabel" | "style"> {
  readonly accessibilityLabel?: string;
  readonly error?: string;
  readonly hint?: string;
  readonly label?: string;
  readonly required?: boolean;
  readonly style?: StyleProp<TextStyle>;
  readonly textDirection?: "auto" | "ltr" | "rtl";
}

function resolveTextDirection(
  explicitDirection: TextFieldProps["textDirection"],
  inputProps: TextInputProps,
): "auto" | "ltr" | "rtl" {
  if (explicitDirection !== undefined) return explicitDirection;

  const technicalKeyboard = inputProps.keyboardType !== undefined && [
    "ascii-capable",
    "decimal-pad",
    "email-address",
    "number-pad",
    "numeric",
    "phone-pad",
    "url",
  ].includes(inputProps.keyboardType);
  const technicalInputMode = inputProps.inputMode !== undefined && [
    "decimal",
    "email",
    "numeric",
    "tel",
    "url",
  ].includes(inputProps.inputMode);

  return inputProps.secureTextEntry || technicalKeyboard || technicalInputMode ? "ltr" : "rtl";
}

export function TextField({
  accessibilityLabel,
  error,
  hint,
  label,
  required = false,
  style,
  textDirection,
  ...textInputProps
}: TextFieldProps) {
  const resolvedTextDirection = resolveTextDirection(textDirection, textInputProps);
  const textStyle = resolvedTextDirection === "auto"
    ? { textAlign: undefined, writingDirection: "auto" as const }
    : getTextDirectionStyle(resolvedTextDirection);

  return (
    <FormField error={error} description={hint} label={label} required={required}>
      <TextInput
        {...textInputProps}
        allowFontScaling={textInputProps.allowFontScaling ?? true}
        accessibilityLabel={accessibilityLabel ?? label}
        accessibilityHint={error ?? textInputProps.accessibilityHint}
        placeholderTextColor={textInputProps.placeholderTextColor ?? fiticianTokens.colors.muted}
        style={[
          styles.input,
          textInputProps.editable === false && styles.inputDisabled,
          error && styles.inputError,
          textStyle,
          style,
        ]}
      />
    </FormField>
  );
}

const styles = StyleSheet.create({
  description: {
    color: fiticianTokens.colors.muted,
  },
  error: {
    color: fiticianTokens.colors.danger,
  },
  field: {
    gap: fiticianTokens.spacing[2],
  },
  input: {
    ...RTL_TEXT,
    backgroundColor: fiticianTokens.colors.surface,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: fiticianTokens.spacing[4],
    paddingVertical: fiticianTokens.spacing[3],
  },
  inputDisabled: {
    opacity: 0.58,
  },
  inputError: {
    borderColor: fiticianTokens.colors.danger,
  },
  label: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.medium,
  },
  required: {
    color: fiticianTokens.colors.coral,
  },
  status: {
    ...RTL_TEXT,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 18,
  },
});
