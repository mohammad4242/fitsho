import { StyleSheet } from "react-native";

import { fiticianTokens } from "../ui/tokens";

export const authStyles = StyleSheet.create({
  accentRule: {
    alignItems: "flex-start",
    backgroundColor: fiticianTokens.colors.line,
    height: 2,
    overflow: "hidden",
    width: "100%",
  },
  accentRuleFill: {
    backgroundColor: fiticianTokens.colors.aqua,
    height: "100%",
    width: "24%",
  },
  brand: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.displayEnglish,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    letterSpacing: 1.4,
    textAlign: "left",
    writingDirection: "ltr",
  },
  brandIcon: {
    color: fiticianTokens.colors.aqua,
  },
  brandLockup: {
    alignItems: "center",
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
  },
  brandMark: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.small,
    borderWidth: 1,
    height: 30,
    justifyContent: "center",
    width: 30,
  },
  brandRow: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
  },
  content: {
    gap: fiticianTokens.spacing[4],
    width: "100%",
  },
  divider: {
    alignItems: "center",
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
  },
  dividerLine: {
    backgroundColor: fiticianTokens.colors.line,
    flex: 1,
    height: 1,
  },
  dividerText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    writingDirection: "rtl",
  },
  footer: {
    alignItems: "center",
    gap: fiticianTokens.spacing[2],
    marginTop: fiticianTokens.spacing[2],
  },
  footerText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "center",
    writingDirection: "rtl",
  },
  formSection: {
    gap: fiticianTokens.spacing[4],
  },
  fieldHeading: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
    minHeight: fiticianTokens.layout.minimumTouchTarget,
  },
  fieldLabel: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.medium,
    textAlign: "right",
    writingDirection: "rtl",
  },
  heading: {
    marginTop: fiticianTokens.spacing[4],
  },
  inlineLink: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: fiticianTokens.spacing[2],
    paddingVertical: fiticianTokens.spacing[2],
    textAlign: "center",
    writingDirection: "rtl",
  },
  link: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: fiticianTokens.spacing[2],
    paddingVertical: fiticianTokens.spacing[2],
    textAlign: "center",
    writingDirection: "rtl",
  },
  panel: {
    alignSelf: "center",
    gap: fiticianTokens.spacing[4],
    maxWidth: 440,
    width: "100%",
  },
  productTag: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  screen: {
    paddingBottom: fiticianTokens.spacing[7],
    paddingTop: fiticianTokens.spacing[4],
  },
});
