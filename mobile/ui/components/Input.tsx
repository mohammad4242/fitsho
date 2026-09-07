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
    <View style={[styles.field, style]}>
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

export function TextField({
  accessibilityLabel,
  error,
  hint,
  label,
  required = false,
  style,
  textDirection = "rtl",
  ...textInputProps
}: TextFieldProps) {
  const textAlign = textDirection === "rtl" ? "right" : textDirection === "ltr" ? "left" : undefined;

  return (
    <FormField error={error} description={hint} label={label} required={required}>
      <TextInput
        {...textInputProps}
        accessibilityLabel={accessibilityLabel ?? label}
        accessibilityHint={error ?? textInputProps.accessibilityHint}
        placeholderTextColor={textInputProps.placeholderTextColor ?? fiticianTokens.colors.muted}
        style={[
          styles.input,
          textInputProps.editable === false && styles.inputDisabled,
          error && styles.inputError,
          { textAlign, writingDirection: textDirection },
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
    writingDirection: "rtl",
  },
  inputDisabled: {
    opacity: 0.58,
  },
  inputError: {
    borderColor: fiticianTokens.colors.danger,
  },
  label: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.medium,
    textAlign: "right",
    writingDirection: "rtl",
  },
  required: {
    color: fiticianTokens.colors.coral,
  },
  status: {
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 18,
    textAlign: "right",
    writingDirection: "rtl",
  },
});
