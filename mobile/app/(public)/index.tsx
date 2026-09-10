import { Pressable, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";

import { authCopy } from "../../auth/copy";
import { AppIcon, Button, CinematicSurface, Media } from "../../ui/components";
import { Screen } from "../../ui/layout";
import { fiticianTokens } from "../../ui/tokens";

const landing = authCopy.landing;

const processStages = [
  ["۰۱", landing.progression.understand.title, landing.progression.understand.body],
  ["۰۲", landing.progression.plan.title, landing.progression.plan.body],
  ["۰۳", landing.progression.train.title, landing.progression.train.body],
  ["۰۴", landing.progression.adapt.title, landing.progression.adapt.body],
] as const;

export default function PublicEntryScreen() {
  const router = useRouter();

  return (
    <Screen contentWidth="full" contentContainerStyle={styles.screen}>
      <View style={styles.header}>
        <Text style={styles.brand}>{authCopy.common.brand}</Text>
        <View style={styles.headerActions}>
          <Pressable accessibilityRole="button" onPress={() => router.push("/auth/sign-in")}>
            <Text style={styles.headerLink}>{landing.menu.signIn}</Text>
          </Pressable>
        </View>
      </View>

      <View style={styles.content}>
        <CinematicSurface accent style={styles.hero} variant="hero">
          <Media
            accessibilityLabel={landing.hero.visualLabel}
            source={require("../../assets/public-entry-hero.jpg")}
            style={styles.heroMedia}
          />
          <View pointerEvents="none" style={styles.heroScrim} />
          <View style={styles.heroContent}>
            <Text accessibilityRole="header" style={styles.heroTitle}>{landing.hero.title}</Text>
            <Text style={styles.body}>{landing.hero.body}</Text>
            <Button label={landing.cta} onPress={() => router.push("/public-onboarding")} />
          </View>
        </CinematicSurface>

        <View style={styles.storySection}>
          <Text style={styles.paperEyebrow}>TRAINING</Text>
          <Text accessibilityRole="header" style={styles.sectionTitle}>{landing.supervision.training.title}</Text>
          <CinematicSurface style={styles.supervisionCard} variant="quiet">
            <View style={styles.planPaper}>
              <Text style={styles.paperEyebrow}>{landing.supervision.training.seal}</Text>
              <Text style={styles.paperTitle}>{landing.progression.plan.title}</Text>
              <View style={styles.paperLine} />
              <View style={styles.paperLineShort} />
              <View style={styles.paperStamp}><AppIcon color={fiticianTokens.colors.aqua} name="check" size={18} /></View>
            </View>
          </CinematicSurface>
        </View>

        <View style={styles.storySection}>
          <Text style={styles.paperEyebrow}>NUTRITION</Text>
          <Text accessibilityRole="header" style={styles.sectionTitle}>{landing.supervision.nutrition.title}</Text>
          <CinematicSurface style={styles.supervisionCard} variant="quiet">
            <View style={styles.planPaper}>
              <Text style={styles.paperEyebrow}>{landing.supervision.nutrition.seal}</Text>
              <Text style={styles.paperTitle}>{landing.progression.plan.title}</Text>
              <View style={styles.paperLine} />
              <View style={styles.paperLineShort} />
              <View style={styles.paperStamp}><AppIcon color={fiticianTokens.colors.aqua} name="check" size={18} /></View>
            </View>
          </CinematicSurface>
        </View>

        <View style={styles.storySection}>
          <Text style={styles.paperEyebrow}>MEAL PHOTO ANALYSIS</Text>
          <Text accessibilityRole="header" style={styles.sectionTitle}>{landing.meal.title}</Text>
          <Text style={styles.muted}>{landing.meal.estimate}</Text>
          <View style={styles.mealCard}>
            <Media
              accessibilityLabel={landing.meal.imageAlt}
              source={require("../../assets/home-food.webp")}
              style={styles.mealImage}
            />
            <View style={styles.mealResult}>
              <Text style={styles.muted}>{landing.meal.resultLabel}</Text>
              <Text style={styles.calories}>{landing.meal.calories}</Text>
              <View style={styles.macroRow}>
                <Macro label={landing.meal.macros.protein.label} value={landing.meal.macros.protein.value} />
                <Macro label={landing.meal.macros.carbs.label} value={landing.meal.macros.carbs.value} />
                <Macro label={landing.meal.macros.fat.label} value={landing.meal.macros.fat.value} />
              </View>
            </View>
          </View>
        </View>

        <View style={styles.storySection} testID="public-entry-process">
          <Text style={styles.eyebrow}>{landing.process.eyebrow}</Text>
          <Text accessibilityRole="header" style={styles.sectionTitle}>{landing.process.title}</Text>
          <View style={styles.processList}>
            {processStages.map(([number, title, body]) => (
              <View key={number} style={styles.processStage}>
                <View style={styles.stageMarker}><Text style={styles.stageNumber}>{number}</Text></View>
                <View style={styles.stageCopy}>
                  <Text style={styles.stageTitle}>{title}</Text>
                  <Text style={styles.muted}>{body}</Text>
                </View>
              </View>
            ))}
          </View>
        </View>

        <View style={styles.storySection}>
          <Text style={styles.eyebrow}>{landing.intelligence.eyebrow}</Text>
          <Text accessibilityRole="header" style={styles.sectionTitle}>{landing.intelligence.title}</Text>
          <Text style={styles.body}>{landing.intelligence.body}</Text>
          <View style={styles.analysisCapture}>
            <Media
              accessibilityLabel={landing.intelligence.analysisImageAlt}
              source={require("../../assets/body-analysis/bodyanalysis.jpg")}
              style={styles.analysisImage}
            />
            <Text style={styles.muted}>{landing.intelligence.scanning}</Text>
          </View>
          <View style={styles.bodyVisual}>
            <Media
              accessibilityLabel={landing.intelligence.imageAlt}
              source={require("../../assets/body-analysis/bodyanalysis.jpg")}
              style={styles.bodyImage}
            />
            <Pressable accessibilityRole="button" accessibilityLabel={landing.callouts.shoulders} style={styles.shoulderHotspot}>
              <View style={styles.hotspotDot} />
            </Pressable>
            <Pressable accessibilityRole="button" accessibilityLabel={landing.callouts.back} style={styles.backHotspot}>
              <View style={styles.hotspotDot} />
            </Pressable>
            <View style={styles.bodyCallout}>
              <Text style={styles.muted}>{landing.callouts.shoulders}</Text>
              <Text style={styles.calloutValue}>{landing.intelligence.muscles.shoulders}</Text>
            </View>
          </View>
        </View>

        <View style={styles.finalSection}>
          <Text accessibilityRole="header" style={styles.sectionTitle}>{landing.final.title}</Text>
          <Button label={landing.final.action} onPress={() => router.push("/public-onboarding")} />
        </View>
      </View>
    </Screen>
  );
}

function Macro({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <View style={styles.macro}>
      <Text style={styles.macroValue}>{value}</Text>
      <Text style={styles.muted}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  backHotspot: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceRaised,
    borderColor: fiticianTokens.colors.aqua,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    bottom: "31%",
    left: "54%",
    paddingHorizontal: fiticianTokens.spacing[2],
    paddingVertical: fiticianTokens.spacing[2],
    position: "absolute",
  },
  analysisCapture: {
    alignItems: "center",
    alignSelf: "center",
    gap: fiticianTokens.spacing[2],
    maxWidth: 260,
    width: "100%",
  },
  analysisImage: {
    borderRadius: fiticianTokens.radii.extraLarge,
    height: 300,
    width: "100%",
  },
  body: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    lineHeight: 28,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  bodyImage: {
    borderRadius: fiticianTokens.radii.extraLarge,
    height: 420,
    width: "100%",
  },
  bodyVisual: {
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.extraLarge,
    borderWidth: 1,
    marginTop: fiticianTokens.spacing[4],
    overflow: "hidden",
    position: "relative",
  },
  bodyCallout: {
    backgroundColor: fiticianTokens.colors.surfaceRaised,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    bottom: fiticianTokens.spacing[4],
    gap: fiticianTokens.spacing[1],
    left: fiticianTokens.spacing[4],
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
    position: "absolute",
  },
  brand: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  calories: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.displayEnglish,
    fontSize: fiticianTokens.typography.fontSize.h2,
    textAlign: "left",
    writingDirection: "ltr",
  },
  content: {
    gap: fiticianTokens.spacing[7],
    width: "100%",
  },
  eyebrow: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    letterSpacing: 0.4,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  finalSection: {
    alignItems: "center",
    gap: fiticianTokens.spacing[4],
    paddingBottom: fiticianTokens.spacing[6],
    paddingTop: fiticianTokens.spacing[4],
  },
  header: {
    alignItems: "center",
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
    width: "100%",
  },
  headerActions: {
    alignItems: "center",
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
  },
  headerLink: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: fiticianTokens.spacing[2],
    paddingVertical: fiticianTokens.spacing[3],
    textAlign: "center",
    writingDirection: "rtl",
  },
  hero: {
    minHeight: 500,
  },
  heroContent: {
    gap: fiticianTokens.spacing[4],
    justifyContent: "flex-end",
    minHeight: 500,
    padding: fiticianTokens.spacing[5],
  },
  heroMedia: {
    borderRadius: 0,
    bottom: 0,
    height: "100%",
    left: 0,
    position: "absolute",
    right: 0,
    top: 0,
    width: "100%",
  },
  heroScrim: {
    backgroundColor: fiticianTokens.colors.mediaOverlay,
    bottom: 0,
    left: 0,
    position: "absolute",
    right: 0,
    top: 0,
  },
  heroTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h1,
    lineHeight: 42,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  hotspotDot: {
    backgroundColor: fiticianTokens.colors.aqua,
    borderColor: fiticianTokens.colors.canvas,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 2,
    height: 12,
    width: 12,
  },
  macro: {
    alignItems: "flex-end",
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  macroRow: {
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
    marginTop: fiticianTokens.spacing[3],
  },
  macroValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayEnglish,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "left",
    writingDirection: "ltr",
  },
  mealCard: {
    backgroundColor: fiticianTokens.colors.surface,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.extraLarge,
    borderWidth: 1,
    overflow: "hidden",
  },
  mealImage: {
    height: 240,
    width: "100%",
  },
  mealResult: {
    gap: fiticianTokens.spacing[2],
    padding: fiticianTokens.spacing[4],
  },
  muted: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 22,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  paperEyebrow: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    letterSpacing: 0.6,
    textAlign: "left",
    writingDirection: "ltr",
  },
  paperLine: {
    backgroundColor: "rgba(2,6,7,0.16)",
    height: 2,
    marginTop: fiticianTokens.spacing[3],
    width: "80%",
  },
  paperLineShort: {
    backgroundColor: "rgba(2,6,7,0.12)",
    height: 2,
    marginTop: fiticianTokens.spacing[2],
    width: "52%",
  },
  paperStamp: {
    alignItems: "center",
    alignSelf: "flex-end",
    borderColor: fiticianTokens.colors.aqua,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    height: 34,
    justifyContent: "center",
    marginTop: fiticianTokens.spacing[4],
    width: 34,
  },
  paperTitle: {
    color: "#15201e",
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    marginTop: fiticianTokens.spacing[3],
    textAlign: "auto",
    writingDirection: "rtl",
  },
  planPaper: {
    backgroundColor: "#d6d2c6",
    borderRadius: fiticianTokens.radii.medium,
    minHeight: 190,
    padding: fiticianTokens.spacing[4],
  },
  processList: {
    gap: fiticianTokens.spacing[2],
  },
  processStage: {
    alignItems: "center",
    borderBottomColor: fiticianTokens.colors.line,
    borderBottomWidth: 1,
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    paddingVertical: fiticianTokens.spacing[3],
  },
  screen: {
    gap: fiticianTokens.spacing[5],
    paddingBottom: fiticianTokens.spacing[7],
    paddingTop: fiticianTokens.spacing[3],
  },
  sectionTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h2,
    lineHeight: 34,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  calloutValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  shoulderHotspot: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceRaised,
    borderColor: fiticianTokens.colors.aqua,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    paddingHorizontal: fiticianTokens.spacing[2],
    paddingVertical: fiticianTokens.spacing[2],
    position: "absolute",
    right: "16%",
    top: "25%",
  },
  stageCopy: {
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  stageMarker: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    height: 34,
    justifyContent: "center",
    width: 34,
  },
  stageNumber: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    writingDirection: "ltr",
  },
  stageTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  storySection: {
    gap: fiticianTokens.spacing[3],
  },
  supervisionCard: {
    flex: 1,
    padding: fiticianTokens.spacing[3],
  },
});
