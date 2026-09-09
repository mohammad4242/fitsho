import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  type StyleProp,
  type ViewStyle,
} from "react-native";
import { type ReactNode } from "react";
import { SafeAreaView } from "react-native-safe-area-context";

import { fiticianTokens } from "../tokens";
import { Button } from "./Button";

interface OverlayBaseProps {
  readonly children?: ReactNode;
  readonly closeLabel?: string;
  readonly onClose: () => void;
  readonly title?: string;
  readonly visible: boolean;
}

export interface SheetProps extends OverlayBaseProps {
  readonly children: ReactNode;
  readonly style?: StyleProp<ViewStyle>;
}

export function Sheet({
  children,
  closeLabel = "Close",
  onClose,
  style,
  title,
  visible,
}: SheetProps) {
  return (
    <Modal
      accessibilityViewIsModal
      animationType="slide"
      onRequestClose={onClose}
      statusBarTranslucent
      transparent
      visible={visible}
    >
      <View style={styles.overlay}>
        <Pressable
          accessibilityLabel={closeLabel}
          accessibilityRole="button"
          onPress={onClose}
          style={StyleSheet.absoluteFill}
        />
        <SafeAreaView edges={["bottom"]} style={[styles.sheet, style]}>
          <View style={styles.header}>
            {title ? <Text style={styles.title}>{title}</Text> : <View />}
            <Pressable
              accessibilityLabel={closeLabel}
              accessibilityRole="button"
              hitSlop={fiticianTokens.spacing[2]}
              onPress={onClose}
              style={styles.close}
            >
              <Text style={styles.closeGlyph}>×</Text>
            </Pressable>
          </View>
          <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
            {children}
          </ScrollView>
        </SafeAreaView>
      </View>
    </Modal>
  );
}

export interface DialogProps extends OverlayBaseProps {
  readonly cancelLabel?: string;
  readonly confirmLabel?: string;
  readonly destructive?: boolean;
  readonly message: string;
  readonly onCancel?: () => void;
  readonly onConfirm?: () => void;
}

export function Dialog({
  cancelLabel = "Cancel",
  closeLabel = "Close",
  confirmLabel = "Confirm",
  destructive = false,
  message,
  onCancel,
  onClose,
  onConfirm,
  title,
  visible,
  children,
}: DialogProps) {
  const cancel = onCancel ?? onClose;

  return (
    <Modal
      accessibilityViewIsModal
      accessibilityLabel={closeLabel}
      animationType="fade"
      onRequestClose={onClose}
      statusBarTranslucent
      transparent
      visible={visible}
    >
      <SafeAreaView edges={["top", "bottom"]} style={styles.dialogOverlay}>
        <View style={styles.dialog}>
          {title ? <Text style={styles.title}>{title}</Text> : null}
          <Text style={styles.message}>{message}</Text>
          {children}
          <View style={styles.actions}>
            <Button label={cancelLabel} onPress={cancel} variant="ghost" />
            {onConfirm ? (
              <Button
                label={confirmLabel}
                onPress={onConfirm}
                variant={destructive ? "danger" : "primary"}
              />
            ) : null}
          </View>
        </View>
      </SafeAreaView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  actions: {
    direction: "rtl",
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
    justifyContent: "flex-end",
    marginTop: fiticianTokens.spacing[5],
  },
  close: {
    alignItems: "center",
    height: fiticianTokens.layout.minimumTouchTarget,
    justifyContent: "center",
    width: fiticianTokens.layout.minimumTouchTarget,
  },
  closeGlyph: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: 28,
    lineHeight: 28,
  },
  content: {
    gap: fiticianTokens.spacing[4],
    paddingBottom: fiticianTokens.spacing[6],
    paddingHorizontal: fiticianTokens.spacing[4],
    paddingTop: fiticianTokens.spacing[3],
  },
  dialog: {
    backgroundColor: fiticianTokens.colors.surfaceRaised,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.large,
    borderWidth: 1,
    elevation: fiticianTokens.shadows.focus.elevation,
    maxWidth: 520,
    padding: fiticianTokens.spacing[5],
    shadowColor: fiticianTokens.shadows.focus.color,
    shadowOffset: fiticianTokens.shadows.focus.offset,
    shadowOpacity: fiticianTokens.shadows.focus.opacity,
    shadowRadius: fiticianTokens.shadows.focus.radius,
    direction: "rtl",
    width: "100%",
  },
  dialogOverlay: {
    alignItems: "center",
    backgroundColor: "rgba(2,6,7,0.78)",
    direction: "rtl",
    flex: 1,
    justifyContent: "center",
    padding: fiticianTokens.spacing[4],
  },
  header: {
    alignItems: "center",
    borderBottomColor: fiticianTokens.colors.line,
    borderBottomWidth: 1,
    flexDirection: "row",
    justifyContent: "space-between",
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: fiticianTokens.spacing[4],
  },
  message: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    lineHeight: 26,
    textAlign: "right",
    writingDirection: "rtl",
  },
  overlay: {
    backgroundColor: "rgba(2,6,7,0.72)",
    direction: "rtl",
    flex: 1,
    justifyContent: "flex-end",
  },
  sheet: {
    backgroundColor: fiticianTokens.colors.surface,
    borderTopLeftRadius: fiticianTokens.radii.extraLarge,
    borderTopRightRadius: fiticianTokens.radii.extraLarge,
    elevation: fiticianTokens.shadows.focus.elevation,
    maxHeight: "88%",
    shadowColor: fiticianTokens.shadows.focus.color,
    shadowOffset: fiticianTokens.shadows.focus.offset,
    shadowOpacity: fiticianTokens.shadows.focus.opacity,
    shadowRadius: fiticianTokens.shadows.focus.radius,
    direction: "rtl",
  },
  title: {
    color: fiticianTokens.colors.ink,
    flex: 1,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    lineHeight: 28,
    textAlign: "right",
    writingDirection: "rtl",
  },
});
