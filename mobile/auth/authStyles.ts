import { StyleSheet } from "react-native";

import { fiticianTokens } from "../ui/tokens";

export const authStyles = StyleSheet.create({
  brand: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  brandRow: {
    alignItems: "center",
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    width: "100%",
  },
  content: {
    gap: fiticianTokens.spacing[5],
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
    textAlign: "center",
    writingDirection: "rtl",
  },
  fieldHeading: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
    minHeight: fiticianTokens.layout.minimumTouchTarget,
  },
  fieldLabel: {
    color: fiticianTokens.colors.ink,
    flex: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.medium,
    textAlign: "right",
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
  heading: {
    marginTop: fiticianTokens.spacing[3],
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
    maxWidth: 432,
    width: "100%",
  },
  screen: {
    paddingBottom: fiticianTokens.spacing[7],
    paddingTop: fiticianTokens.spacing[4],
  },
});
