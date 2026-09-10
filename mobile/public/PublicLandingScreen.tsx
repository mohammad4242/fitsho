import { useCallback, useEffect, useRef, useState } from "react";
import {
  AccessibilityInfo,
  Animated,
  Image,
  Pressable,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
  type ScrollView,
} from "react-native";
import { useRouter } from "expo-router";
import Svg, { Circle, Defs, Path, RadialGradient, Stop } from "react-native-svg";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { authCopy } from "../auth/copy";
import { BrandMark, Button, Media } from "../ui/components";
import { Screen } from "../ui/layout";
import { LTR_TEXT } from "../ui/rtl";
import { fiticianTokens } from "../ui/tokens";

const landing = authCopy.landing;
const landingBackground = "#020b0c";
const processStages = ["understand", "plan", "train", "adapt"] as const;
const muscles = ["shoulders", "back"] as const;
type Muscle = (typeof muscles)[number];

export function PublicLandingScreen() {
  const router = useRouter();
  const scrollRef = useRef<ScrollView>(null);
  const { height, width } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const reducedMotion = useReducedMotion();
  const [scrollOffset, setScrollOffset] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);
  const viewportHeight = Math.max(1, height - insets.top - insets.bottom);
  const compactLayout = width <= 650;
  const cinematicHeight = viewportHeight * (compactLayout ? 4.05 : 3.9);
  const processHeight = viewportHeight * (compactLayout ? 2.2 : 2);
  const bodyHeight = viewportHeight * 2.25;
  const processStart = cinematicHeight;
  const bodyStart = cinematicHeight + processHeight;
  const wideLayout = width >= 900;
  const splitLayout = width > 650;

  const handleScroll = useCallback((event: NativeSyntheticEvent<NativeScrollEvent>) => {
    setScrollOffset(event.nativeEvent.contentOffset.y);
  }, []);

  const scrollTo = useCallback((offset: number) => {
    setMenuOpen(false);
    scrollRef.current?.scrollTo({ animated: true, y: offset });
  }, []);

  return (
    <Screen contentContainerStyle={styles.screenContent} contentWidth="full" scroll={false}>
      <View style={styles.root}>
        <Animated.ScrollView
          contentContainerStyle={styles.scrollContent}
          onScroll={handleScroll}
          ref={scrollRef}
          scrollEventThrottle={16}
          showsVerticalScrollIndicator={false}
          style={styles.scroll}
          testID="public-entry-scroll"
        >
          <PublicCinematicStory
            onStart={() => router.push("/public-onboarding")}
            reducedMotion={reducedMotion}
            scrollOffset={scrollOffset}
            sectionHeight={cinematicHeight}
            sectionStart={0}
            viewportHeight={viewportHeight}
            viewportWidth={width}
            compactLayout={compactLayout}
            splitLayout={splitLayout}
            wideLayout={wideLayout}
          />
          <PublicProcessStory
            compactLayout={compactLayout}
            reducedMotion={reducedMotion}
            scrollOffset={scrollOffset}
            sectionHeight={processHeight}
            sectionStart={processStart}
            viewportHeight={viewportHeight}
          />
          <PublicBodyIntelligence
            compactLayout={compactLayout}
            reducedMotion={reducedMotion}
            scrollOffset={scrollOffset}
            sectionHeight={bodyHeight}
            sectionStart={bodyStart}
            viewportHeight={viewportHeight}
            viewportWidth={width}
            wideLayout={wideLayout}
          />
          <LandingFinal compactLayout={compactLayout} onStart={() => router.push("/public-onboarding")} viewportHeight={viewportHeight} />
        </Animated.ScrollView>

        <LandingHeader
          menuOpen={menuOpen}
          onCloseMenu={() => setMenuOpen(false)}
          onOpenMenu={() => setMenuOpen(true)}
          onScrollToAnalysis={() => scrollTo(bodyStart)}
          onScrollToProcess={() => scrollTo(processStart)}
          onBrandPress={() => router.replace("/")}
          onSignIn={() => router.push("/auth/sign-in")}
          onStart={() => router.push("/public-onboarding")}
          wideLayout={wideLayout}
        />
        {menuOpen ? (
          <LandingMenu
            onClose={() => setMenuOpen(false)}
            onScrollToAnalysis={() => scrollTo(bodyStart)}
            onScrollToProcess={() => scrollTo(processStart)}
            onSignIn={() => {
              setMenuOpen(false);
              router.push("/auth/sign-in");
            }}
            onStart={() => {
              setMenuOpen(false);
              router.push("/public-onboarding");
            }}
          />
        ) : null}
      </View>
    </Screen>
  );
}

function LandingHeader({
  menuOpen,
  onCloseMenu,
  onBrandPress,
  onOpenMenu,
  onScrollToAnalysis,
  onScrollToProcess,
  onSignIn,
  onStart,
  wideLayout,
}: {
  readonly menuOpen: boolean;
  readonly onCloseMenu: () => void;
  readonly onBrandPress: () => void;
  readonly onOpenMenu: () => void;
  readonly onScrollToAnalysis: () => void;
  readonly onScrollToProcess: () => void;
  readonly onSignIn: () => void;
  readonly onStart: () => void;
  readonly wideLayout: boolean;
}) {
  return (
    <View style={styles.header}>
      <BrandMark
        accessibilityLabel={authCopy.common.brand}
        label={authCopy.common.brand}
        onPress={onBrandPress}
        testID="public-entry-brand-mark"
      />
      {wideLayout ? (
        <View style={styles.headerNav}>
          <Pressable accessibilityRole="button" onPress={onScrollToProcess} style={styles.headerLink}>
            <Text style={styles.headerLinkText}>{landing.menu.how}</Text>
          </Pressable>
          <Pressable accessibilityRole="button" onPress={onScrollToAnalysis} style={styles.headerLink}>
            <Text style={styles.headerLinkText}>{landing.menu.analysis}</Text>
          </Pressable>
          <Pressable accessibilityRole="button" onPress={onSignIn} style={styles.headerLink}>
            <Text style={styles.headerLinkText}>{landing.menu.signIn}</Text>
          </Pressable>
        </View>
      ) : null}
      <View style={styles.headerActions}>
        {wideLayout ? (
          <Pressable accessibilityRole="button" onPress={onStart} style={styles.headerBuildButton}>
            <Text style={styles.headerBuildText}>{landing.menu.build}</Text>
          </Pressable>
        ) : (
          <Pressable
            accessibilityLabel={menuOpen ? landing.menu.close : landing.menu.open}
            accessibilityRole="button"
            onPress={menuOpen ? onCloseMenu : onOpenMenu}
            style={styles.menuButton}
          >
            <View style={styles.menuLine} />
            <View style={styles.menuLineShort} />
          </Pressable>
        )}
      </View>
    </View>
  );
}

function LandingMenu({ onClose, onScrollToAnalysis, onScrollToProcess, onSignIn, onStart }: {
  readonly onClose: () => void;
  readonly onScrollToAnalysis: () => void;
  readonly onScrollToProcess: () => void;
  readonly onSignIn: () => void;
  readonly onStart: () => void;
}) {
  return (
    <View accessibilityLabel={landing.menu.label} accessibilityRole="menu" style={styles.menu} testID="public-entry-menu">
      <Pressable accessibilityLabel={landing.menu.close} accessibilityRole="button" onPress={onClose} style={styles.menuClose}>
        <Text style={styles.menuCloseText}>×</Text>
      </Pressable>
      <View style={styles.menuLinks}>
        <MenuLink label={landing.menu.how} onPress={onScrollToProcess} />
        <MenuLink label={landing.menu.analysis} onPress={onScrollToAnalysis} />
        <MenuLink label={landing.menu.build} onPress={onStart} />
        <MenuLink label={landing.menu.signIn} onPress={onSignIn} />
      </View>
    </View>
  );
}

function MenuLink({ label, onPress }: { readonly label: string; readonly onPress: () => void }) {
  return (
    <Pressable accessibilityLabel={label} accessibilityRole="button" onPress={onPress} style={styles.menuLink}>
      <Text style={styles.menuLinkText}>{label}</Text>
    </Pressable>
  );
}

function PublicCinematicStory({ compactLayout, onStart, reducedMotion, scrollOffset, sectionHeight, sectionStart, splitLayout, viewportHeight, viewportWidth, wideLayout }: {
  readonly compactLayout: boolean;
  readonly onStart: () => void;
  readonly reducedMotion: boolean;
  readonly scrollOffset: number;
  readonly sectionHeight: number;
  readonly sectionStart: number;
  readonly splitLayout: boolean;
  readonly viewportHeight: number;
  readonly viewportWidth: number;
  readonly wideLayout: boolean;
}) {
  const storyProgress = reducedMotion ? 1 : sectionProgress(scrollOffset, sectionStart, sectionHeight, viewportHeight);
  const stageTranslation = reducedMotion ? 0 : storyProgress * Math.max(0, sectionHeight - viewportHeight);
  const heroProgress = reducedMotion ? 1 : 1 - progressBetween(storyProgress, 0.04, 0.16);
  const cinemaProgress = reducedMotion ? 0 : progressBetween(storyProgress, 0.06, 0.58);
  const trainingProgress = reducedMotion ? 1 : windowedProgress(storyProgress, 0.14, 0.21, 0.33, 0.44);
  const trainingSeal = reducedMotion ? 1 : progressBetween(storyProgress, 0.23, 0.31);
  const nutritionProgress = reducedMotion ? 1 : windowedProgress(storyProgress, 0.38, 0.46, 0.61, 0.72);
  const nutritionSeal = reducedMotion ? 1 : progressBetween(storyProgress, 0.49, 0.57);
  const mealProgress = reducedMotion ? 1 : progressBetween(storyProgress, 0.64, 0.72);
  const mealScan = reducedMotion ? 1 : progressBetween(storyProgress, 0.73, 0.87);
  const mealResult = reducedMotion ? 1 : progressBetween(storyProgress, 0.86, 0.94);
  const videoProgress = reducedMotion ? 0 : 1 - progressBetween(storyProgress, 0.76, 1);
  const stageStyles = reducedMotion
    ? [styles.reducedCinematicStage]
    : [styles.cinematicStage, { height: viewportHeight, transform: [{ translateY: stageTranslation }] }];

  return (
    <View accessibilityLabel={landing.story.label} style={[styles.cinematicSection, { height: sectionHeight }]} testID="public-entry-cinematic-story">
      <Animated.View style={stageStyles}>
        <PublicLandingFilm reducedMotion={reducedMotion} videoOpacity={0.08 + videoProgress * 0.92} videoScale={1.015 + cinemaProgress * 0.015} />
        <View pointerEvents="none" style={[styles.cinematicShade, compactLayout && styles.cinematicShadeCompact, { opacity: 0.36 + cinemaProgress * 0.5 }]} />
        <View pointerEvents="none" style={[styles.cinematicFade, { opacity: 1 - videoProgress }]} />
        <Animated.View
          pointerEvents={reducedMotion || heroProgress > 0.08 ? "auto" : "none"}
          style={[styles.cinematicScene, compactLayout && styles.cinematicSceneCompact, styles.heroScene, compactLayout && styles.heroSceneCompact, reducedMotion && styles.reducedScene, compactLayout && { paddingBottom: viewportHeight * 0.08 }, { opacity: reducedMotion ? 1 : heroProgress, transform: [{ translateY: reducedMotion ? 0 : (1 - heroProgress) * -24 }] }]}
        >
          <View style={styles.heroCopy}>
            <Text accessibilityRole="header" style={[styles.heroTitle, compactLayout && styles.heroTitleCompact]}>{landing.hero.title}</Text>
            <Text style={[styles.heroBody, compactLayout && styles.heroBodyCompact]}>{landing.hero.body}</Text>
            <Button label={landing.cta} onPress={onStart} style={styles.cta}>{`${landing.cta}  ←`}</Button>
          </View>
          {!reducedMotion ? <View pointerEvents="none" style={styles.scrollIndicator}><View style={styles.scrollIndicatorFill} /></View> : null}
        </Animated.View>
        <SupervisionMoment compactLayout={compactLayout} label="training" progress={trainingProgress} reducedMotion={reducedMotion} sealProgress={trainingSeal} splitLayout={splitLayout} viewportWidth={viewportWidth} wideLayout={wideLayout} />
        <SupervisionMoment compactLayout={compactLayout} label="nutrition" progress={nutritionProgress} reducedMotion={reducedMotion} sealProgress={nutritionSeal} splitLayout={splitLayout} viewportWidth={viewportWidth} wideLayout={wideLayout} />
        <MealPhotoAnalysis compactLayout={compactLayout} mealProgress={mealProgress} mealResult={mealResult} mealScan={mealScan} reducedMotion={reducedMotion} splitLayout={splitLayout} viewportWidth={viewportWidth} />
      </Animated.View>
    </View>
  );
}

function PublicLandingFilm({ reducedMotion, videoOpacity, videoScale }: { readonly reducedMotion: boolean; readonly videoOpacity: number; readonly videoScale: number }) {
  const [failed, setFailed] = useState(false);
  return (
    <View pointerEvents="none" style={styles.filmLayer} testID="public-entry-film">
      <Animated.View style={[styles.filmMediaLayer, { opacity: videoOpacity, transform: [{ scale: videoScale }] }]}>
        <Image accessible={false} resizeMode="cover" source={require("../assets/landing/landfilm-poster.webp")} style={styles.filmMedia} />
        {!reducedMotion && !failed ? (
          <Media autoplay kind="video" loop muted onError={() => setFailed(true)} source={require("../assets/landing/landfilm.mp4")} style={styles.filmMedia} />
        ) : null}
      </Animated.View>
    </View>
  );
}

function SupervisionMoment({ compactLayout, label, progress, reducedMotion, sealProgress, splitLayout, viewportWidth, wideLayout }: { readonly compactLayout: boolean; readonly label: "training" | "nutrition"; readonly progress: number; readonly reducedMotion: boolean; readonly sealProgress: number; readonly splitLayout: boolean; readonly viewportWidth: number; readonly wideLayout: boolean }) {
  const title = label === "training" ? landing.supervision.training.title : landing.supervision.nutrition.title;
  const seal = label === "training" ? landing.supervision.training.seal : landing.supervision.nutrition.seal;
  return (
    <Animated.View
      pointerEvents={reducedMotion || progress > 0.08 ? "auto" : "none"}
      style={[styles.cinematicScene, compactLayout && styles.cinematicSceneCompact, styles.supervisionScene, splitLayout && styles.supervisionSceneWide, compactLayout && styles.supervisionSceneCompact, reducedMotion && styles.reducedScene, { opacity: reducedMotion ? 1 : progress, transform: [{ translateY: reducedMotion ? 0 : (1 - progress) * 32 }] }]}
      testID={`public-entry-supervision-${label}`}
    >
      <View style={[styles.sceneCopy, compactLayout && styles.sceneCopyCompact]}>
        <Text style={styles.sceneEyebrow}>{label.toUpperCase()}</Text>
        <Text accessibilityRole="header" style={[styles.sceneTitle, compactLayout && styles.sceneTitleCompact]}>{title}</Text>
      </View>
      <PlanDocument compactLayout={compactLayout} label={label} seal={seal} sealProgress={sealProgress} viewportWidth={viewportWidth} wideLayout={wideLayout} />
    </Animated.View>
  );
}

function PlanDocument({ compactLayout, label, seal, sealProgress, viewportWidth, wideLayout }: { readonly compactLayout: boolean; readonly label: "training" | "nutrition"; readonly seal: string; readonly sealProgress: number; readonly viewportWidth: number; readonly wideLayout: boolean }) {
  return (
    <View style={[styles.planPaper, compactLayout && styles.planPaperCompact, label === "nutrition" && styles.planPaperNutrition, wideLayout && styles.planPaperWide, compactLayout && { width: Math.min(viewportWidth * 0.72, 272) }]} testID={`public-entry-plan-document-${label}`}>
      <View style={[styles.planHeader, compactLayout && styles.planHeaderCompact]}><View style={[styles.planAvatar, compactLayout && styles.planAvatarCompact]} /><View style={styles.planHeaderLine} /></View>
      <View style={[styles.planContent, compactLayout && styles.planContentCompact]}>
        <View style={[styles.planGroup, compactLayout && styles.planGroupCompact]}><View style={styles.planLineWide} /><View style={styles.planLineMedium} /><View style={styles.planLineShort} /></View>
        <View style={[styles.planGroupTiles, compactLayout && styles.planGroupTilesCompact]}><View style={[styles.planTile, compactLayout && styles.planTileCompact]} /><View style={[styles.planTile, compactLayout && styles.planTileCompact]} /></View>
        <View style={[styles.planGroup, compactLayout && styles.planGroupCompact]}><View style={styles.planLineWide} /><View style={styles.planLineMedium} /><View style={styles.planLineShort} /></View>
      </View>
      <VerificationSeal compactLayout={compactLayout} progress={sealProgress} text={seal} />
    </View>
  );
}

function VerificationSeal({ compactLayout, progress, text }: { readonly compactLayout: boolean; readonly progress: number; readonly text: string }) {
  const size = compactLayout ? 76 : 92;
  const radius = compactLayout ? 31 : 38;
  const center = size / 2;
  const circumference = 2 * Math.PI * radius;
  return (
    <View style={[styles.verificationSeal, compactLayout && styles.verificationSealCompact]}>
      <Svg height={size} width={size}>
        <Circle cx={center} cy={center} fill="transparent" r={radius} stroke="rgba(102,200,159,0.16)" strokeWidth={2} />
        <Circle cx={center} cy={center} fill="transparent" origin={`${center}, ${center}`} r={radius} rotation="-90" stroke={fiticianTokens.colors.success} strokeDasharray={`${circumference} ${circumference}`} strokeDashoffset={circumference * (1 - progress)} strokeLinecap="round" strokeWidth={2} />
        <Path d={compactLayout ? "M23 38 33 48 54 27" : "M28 46 40 58 65 32"} fill="transparent" opacity={progressBetween(progress, 0.72, 1)} stroke={fiticianTokens.colors.success} strokeLinecap="round" strokeLinejoin="round" strokeWidth={compactLayout ? 5 : 6} />
      </Svg>
      <Text style={styles.verificationSealText}>{text}</Text>
    </View>
  );
}

function MealPhotoAnalysis({ compactLayout, mealProgress, mealResult, mealScan, reducedMotion, splitLayout, viewportWidth }: { readonly compactLayout: boolean; readonly mealProgress: number; readonly mealResult: number; readonly mealScan: number; readonly reducedMotion: boolean; readonly splitLayout: boolean; readonly viewportWidth: number }) {
  return (
    <Animated.View
      pointerEvents={reducedMotion || mealProgress > 0.08 ? "auto" : "none"}
      style={[styles.cinematicScene, compactLayout && styles.cinematicSceneCompact, styles.mealScene, splitLayout && styles.mealSceneWide, compactLayout && styles.mealSceneCompact, reducedMotion && styles.reducedScene, { opacity: reducedMotion ? 1 : mealProgress, transform: [{ translateY: reducedMotion ? 0 : (1 - mealProgress) * 29 }] }]}
    >
      <View style={[styles.sceneCopy, compactLayout && styles.sceneCopyCompact]}>
        <Text style={styles.sceneEyebrow}>MEAL PHOTO ANALYSIS</Text>
        <Text accessibilityRole="header" style={[styles.sceneTitle, compactLayout && styles.sceneTitleCompact]}>{landing.meal.title}</Text>
        <Text style={styles.sceneNote}>{landing.meal.estimate}</Text>
      </View>
      <View style={styles.mealVisual}>
        <View style={[styles.scanFrame, compactLayout && styles.scanFrameMealCompact, compactLayout && { width: Math.min(viewportWidth * 0.76, 288) }]} testID="public-entry-meal-scan">
          <Image accessibilityLabel={landing.meal.imageAlt} resizeMode="cover" source={require("../assets/landing/food.webp")} style={styles.scanImage} />
          <ScanCorners progress={mealScan} />
          <View style={[styles.scanLine, { opacity: progressBetween(mealScan, 0, 0.5), top: `${8 + mealScan * 84}%` }]} />
        </View>
        <View style={[styles.mealResult, compactLayout && styles.mealResultCompact, { opacity: reducedMotion ? 1 : mealResult, transform: [{ translateY: reducedMotion ? 0 : (1 - mealResult) * 13 }] }]}>
          <Text style={[styles.mealCalories, LTR_TEXT]}>{landing.meal.calories}</Text>
          <View style={styles.macroRow}>
            {(["protein", "carbs", "fat"] as const).map((macro) => (
              <View key={macro} style={styles.macro}>
                <Text style={styles.macroLabel}>{landing.meal.macros[macro].label}</Text>
                <Text style={[styles.macroValue, LTR_TEXT]}>{landing.meal.macros[macro].value}</Text>
              </View>
            ))}
          </View>
        </View>
      </View>
    </Animated.View>
  );
}

function ScanCorners({ progress }: { readonly progress: number }) {
  return (
    <>
      <View style={[styles.scanCorner, styles.scanCornerOne, { opacity: progress }]} />
      <View style={[styles.scanCorner, styles.scanCornerTwo, { opacity: progress }]} />
      <View style={[styles.scanCorner, styles.scanCornerThree, { opacity: progress }]} />
      <View style={[styles.scanCorner, styles.scanCornerFour, { opacity: progress }]} />
    </>
  );
}

function PublicProcessStory({ compactLayout, reducedMotion, scrollOffset, sectionHeight, sectionStart, viewportHeight }: { readonly compactLayout: boolean; readonly reducedMotion: boolean; readonly scrollOffset: number; readonly sectionHeight: number; readonly sectionStart: number; readonly viewportHeight: number }) {
  const processProgress = reducedMotion ? 1 : sectionProgress(scrollOffset, sectionStart, sectionHeight, viewportHeight);
  const stageTranslation = reducedMotion ? 0 : processProgress * Math.max(0, sectionHeight - viewportHeight);
  return (
    <View accessibilityLabel={landing.progression.label} style={[styles.processSection, { height: sectionHeight }]} testID="public-entry-process">
      <Animated.View style={[reducedMotion ? styles.reducedProcessStage : styles.processStage, compactLayout && styles.processStageCompact, !reducedMotion && { height: viewportHeight, transform: [{ translateY: stageTranslation }] }]}>
        <View style={styles.processHeader}>
          <Text style={styles.landingKicker}>{landing.process.eyebrow}</Text>
          <Text accessibilityRole="header" style={[styles.processTitle, compactLayout && styles.processTitleCompact]}>{landing.process.title}</Text>
        </View>
        <View style={[styles.processList, compactLayout && styles.processListCompact]}>
          {processStages.map((stage, index) => {
            const stepFill = reducedMotion ? 1 : progressBetween(processProgress, index * 0.25, index * 0.25 + 0.14);
            const copyFill = reducedMotion ? 1 : progressBetween(processProgress, index * 0.25 + 0.14, index * 0.25 + 0.18);
            const lineFill = index < processStages.length - 1 ? reducedMotion ? 1 : progressBetween(processProgress, index * 0.25 + 0.18, index * 0.25 + 0.25) : 0;
            return (
              <View key={stage} style={[styles.processStep, compactLayout && styles.processStepCompact]} testID={`public-entry-process-step-${stage}`}>
                <ProgressRing compactLayout={compactLayout} fill={stepFill} number={String(index + 1).padStart(2, "0")} />
                <View style={[styles.processStepCopy, compactLayout && styles.processStepCopyCompact, { opacity: 0.26 + copyFill * 0.74 }]}>
                  <Text style={styles.processStepEyebrow}>{landing.progression[stage].title}</Text>
                  <Text style={[styles.processStepTitle, compactLayout && styles.processStepTitleCompact]}>{landing.progression[stage].body}</Text>
                </View>
                {index < processStages.length - 1 ? <View pointerEvents="none" style={[styles.processConnectorTrack, compactLayout && styles.processConnectorTrackCompact]}><View style={[styles.processConnectorFill, { height: `${lineFill * 100}%` }]} /></View> : null}
              </View>
            );
          })}
        </View>
      </Animated.View>
    </View>
  );
}

function ProgressRing({ compactLayout, fill, number }: { readonly compactLayout: boolean; readonly fill: number; readonly number: string }) {
  const size = compactLayout ? 64 : 70;
  const center = size / 2;
  const radius = compactLayout ? 25 : 28;
  const circumference = 2 * Math.PI * radius;
  return (
    <View style={[styles.progressRing, compactLayout && styles.progressRingCompact]}>
      <Svg height={size} width={size}>
        <Circle cx={center} cy={center} fill="transparent" r={radius} stroke="rgba(232,244,241,0.14)" strokeWidth={2} />
        <Circle cx={center} cy={center} fill="transparent" origin={`${center}, ${center}`} r={radius} rotation="-90" stroke={fiticianTokens.colors.aqua} strokeDasharray={`${circumference} ${circumference}`} strokeDashoffset={circumference * (1 - fill)} strokeLinecap="round" strokeWidth={2} />
      </Svg>
      <Text style={styles.progressRingNumber}>{number}</Text>
    </View>
  );
}

function PublicBodyIntelligence({ compactLayout, reducedMotion, scrollOffset, sectionHeight, sectionStart, viewportHeight, viewportWidth, wideLayout }: { readonly compactLayout: boolean; readonly reducedMotion: boolean; readonly scrollOffset: number; readonly sectionHeight: number; readonly sectionStart: number; readonly viewportHeight: number; readonly viewportWidth: number; readonly wideLayout: boolean }) {
  const bodyProgress = reducedMotion ? 1 : sectionProgress(scrollOffset, sectionStart, sectionHeight, viewportHeight);
  const stageTranslation = reducedMotion ? 0 : bodyProgress * Math.max(0, sectionHeight - viewportHeight);
  const analysisProgress = reducedMotion ? 1 : progressBetween(bodyProgress, 0.08, 0.46);
  const analysisExit = reducedMotion ? 0 : progressBetween(bodyProgress, 0.48, 0.66);
  const bodyResult = reducedMotion ? 1 : progressBetween(bodyProgress, 0.58, 0.72);
  const bodyDepth = reducedMotion ? 1 : progressBetween(bodyProgress, 0.58, 1);
  const captureOpacity = analysisProgress * (1 - analysisExit);
  const [activeMuscle, setActiveMuscle] = useState<Muscle>("shoulders");
  return (
    <View accessibilityLabel={landing.intelligence.title} style={[styles.bodySection, { height: sectionHeight }]} testID="public-entry-body-story">
      <Animated.View style={[reducedMotion ? styles.reducedBodyStage : styles.bodyStage, compactLayout && styles.bodyStageCompact, !reducedMotion && { height: viewportHeight, transform: [{ translateY: stageTranslation }] }]}>
        <View style={[styles.bodyHeading, compactLayout && styles.bodyHeadingCompact]}>
          <Text style={styles.landingKicker}>{landing.intelligence.eyebrow}</Text>
          <Text accessibilityRole="header" style={[styles.bodyTitle, compactLayout && styles.bodyTitleCompact]}>{landing.intelligence.title}</Text>
          <Text style={[styles.bodyDescription, compactLayout && styles.bodyDescriptionCompact]}>{landing.intelligence.body}</Text>
        </View>
        <Animated.View style={[styles.bodyCapture, compactLayout && styles.bodyCaptureCompact, wideLayout && styles.bodyCaptureWide, { opacity: captureOpacity, transform: [{ translateY: reducedMotion ? 0 : analysisExit * -11.2 }, { scale: reducedMotion ? 1 : 1 - analysisExit * 0.025 }] }]}>
          <View style={[styles.bodyScanFrame, compactLayout && styles.bodyScanFrameCompact, compactLayout && { width: Math.min(viewportWidth * 0.72, 272) }]}>
            <Image accessibilityLabel={landing.intelligence.analysisImageAlt} resizeMode="cover" source={require("../assets/landing/analyze.webp")} style={styles.bodyCaptureImage} />
            <ScanCorners progress={analysisProgress} />
            <View style={[styles.scanLine, { opacity: progressBetween(analysisProgress, 0, 0.5), top: `${8 + analysisProgress * 84}%` }]} />
            <View pointerEvents="none" style={[styles.bodyMapping, { opacity: analysisProgress }]}>
              <View style={[styles.bodyMappingDot, styles.bodyMappingOne]} />
              <View style={[styles.bodyMappingDot, styles.bodyMappingTwo]} />
              <View style={[styles.bodyMappingDot, styles.bodyMappingThree]} />
            </View>
          </View>
          <Text style={styles.bodyCaptureLabel}>{landing.intelligence.scanning}</Text>
        </Animated.View>
        <Animated.View style={[styles.bodyInterface, compactLayout && styles.bodyInterfaceCompact, wideLayout && styles.bodyInterfaceWide, { opacity: bodyResult, transform: [{ translateY: reducedMotion ? 0 : (1 - bodyResult) * 12 + (bodyDepth - 0.5) * -5.6 }] }]} testID="public-entry-body-analysis">
          <Image accessibilityLabel={landing.intelligence.imageAlt} resizeMode="cover" source={require("../assets/landing/body.webp")} style={styles.bodyInterfaceImage} />
          <Svg pointerEvents="none" style={styles.bodyMuscles} viewBox="0 0 100 150">
            <Defs>
              <RadialGradient id="body-muscle-aqua" cx="50%" cy="42%" r="68%">
                <Stop offset="0" stopColor="#9ff8ed" stopOpacity={0.55} />
                <Stop offset="0.48" stopColor="#50dfce" stopOpacity={0.26} />
                <Stop offset="1" stopColor="#50dfce" stopOpacity={0} />
              </RadialGradient>
            </Defs>
            <Path d="M22 35 C22 27 29 23 38 25 C43 26 47 30 49 35 C42 34 36 36 30 43 C25 43 22 40 22 35 Z M51 35 C53 30 57 26 62 25 C71 23 78 27 78 35 C78 40 75 43 70 43 C64 36 58 34 51 35 Z" fill="url(#body-muscle-aqua)" opacity={activeMuscle === "shoulders" ? 0.42 : 0} />
            <Path d="M24 34 C25 28 31 26 38 27 C42 28 45 31 47 34 C40 34 34 37 30 41 C27 41 24 38 24 34 Z M53 34 C55 31 58 28 62 27 C69 26 75 28 76 34 C76 38 73 41 70 41 C66 37 60 34 53 34 Z" fill="url(#body-muscle-aqua)" opacity={activeMuscle === "shoulders" ? 0.17 : 0} />
            <Path d="M33 36 C39 32 45 33 50 39 C55 33 61 32 67 36 L69 58 C64 68 58 74 50 77 C42 74 36 68 31 58 Z" fill="url(#body-muscle-aqua)" opacity={activeMuscle === "back" ? 0.42 : 0} />
            <Path d="M36 37 C41 34 46 36 50 41 C54 36 59 34 64 37 L66 56 C62 64 57 69 50 72 C43 69 38 64 34 56 Z" fill="url(#body-muscle-aqua)" opacity={activeMuscle === "back" ? 0.17 : 0} />
          </Svg>
          <Svg pointerEvents="none" style={styles.bodyConnectors} viewBox="0 0 100 150">
            <Path d="M72 34 C80 34 82 30 90 30" fill="none" opacity={activeMuscle === "shoulders" ? 1 : 0} stroke={fiticianTokens.colors.aqua} strokeDasharray="4 4" strokeWidth="0.8" />
            <Path d="M58 57 C73 57 78 74 90 74" fill="none" opacity={activeMuscle === "back" ? 1 : 0} stroke={fiticianTokens.colors.aqua} strokeDasharray="4 4" strokeWidth="0.8" />
          </Svg>
          <Pressable accessibilityLabel={landing.callouts.shoulders} accessibilityRole="button" accessibilityState={{ selected: activeMuscle === "shoulders" }} onPress={() => setActiveMuscle("shoulders")} style={[styles.bodyHotspot, styles.shoulderHotspot, activeMuscle === "shoulders" ? styles.bodyHotspotActive : styles.bodyHotspotInactive]}><View style={styles.hotspotDot} /></Pressable>
          <Pressable accessibilityLabel={landing.callouts.back} accessibilityRole="button" accessibilityState={{ selected: activeMuscle === "back" }} onPress={() => setActiveMuscle("back")} style={[styles.bodyHotspot, styles.backHotspot, activeMuscle === "back" ? styles.bodyHotspotActive : styles.bodyHotspotInactive]}><View style={styles.hotspotDot} /></Pressable>
          <View accessibilityLiveRegion="polite" style={[styles.bodyCallout, compactLayout && styles.bodyCalloutCompact, activeMuscle === "back" && (compactLayout ? styles.bodyCalloutBackCompact : styles.bodyCalloutBack)]}>
            <Text style={styles.bodyCalloutLabel}>{landing.callouts[activeMuscle]}</Text>
            <Text style={styles.bodyCalloutValue}>{landing.intelligence.muscles[activeMuscle]}</Text>
          </View>
        </Animated.View>
      </Animated.View>
    </View>
  );
}

function LandingFinal({ compactLayout, onStart, viewportHeight }: { readonly compactLayout: boolean; readonly onStart: () => void; readonly viewportHeight: number }) {
  return (
    <View style={[styles.finalSection, { minHeight: compactLayout ? viewportHeight * 0.48 : Math.min(544, Math.max(400, viewportHeight * 0.56)) }]}>
      <Text accessibilityRole="header" style={styles.finalTitle}>{landing.final.title}</Text>
      <Button label={landing.final.action} onPress={onStart} style={styles.cta}>{`${landing.final.action}  ←`}</Button>
    </View>
  );
}

function useReducedMotion() {
  const [reducedMotion, setReducedMotion] = useState(false);
  useEffect(() => {
    const subscription = AccessibilityInfo.addEventListener("reduceMotionChanged", setReducedMotion);
    return () => subscription.remove();
  }, []);
  return reducedMotion;
}

function clamp(value: number) {
  return Math.min(1, Math.max(0, value));
}

function progressBetween(value: number, start: number, end: number) {
  return clamp((value - start) / Math.max(0.0001, end - start));
}

function windowedProgress(value: number, enterStart: number, enterEnd: number, exitStart: number, exitEnd: number) {
  return Math.min(progressBetween(value, enterStart, enterEnd), 1 - progressBetween(value, exitStart, exitEnd));
}

function sectionProgress(offset: number, start: number, height: number, viewportHeight: number) {
  return progressBetween(offset, start, start + Math.max(1, height - viewportHeight));
}

const styles = StyleSheet.create({
  screenContent: { paddingHorizontal: 0 },
  root: { backgroundColor: landingBackground, flex: 1 },
  scroll: { backgroundColor: landingBackground, flex: 1 },
  scrollContent: { backgroundColor: landingBackground, paddingBottom: 24 },
  header: { alignItems: "center", backgroundColor: "rgba(2,11,12,0.72)", borderBottomColor: "rgba(232,244,241,0.06)", borderBottomWidth: 1, flexDirection: "row", justifyContent: "space-between", left: 0, minHeight: 76, paddingHorizontal: 16, position: "absolute", right: 0, top: 0, zIndex: 20 },
  brand: { color: fiticianTokens.colors.mist, fontFamily: fiticianTokens.typography.fontFamily.bodyPersian, fontSize: 20, fontWeight: "800", writingDirection: "rtl" },
  headerNav: { alignItems: "center", flexDirection: "row", gap: 4 },
  headerLink: { minHeight: 48, justifyContent: "center", paddingHorizontal: 12 },
  headerLinkText: { color: fiticianTokens.colors.muted, fontFamily: fiticianTokens.typography.fontFamily.bodyPersian, fontSize: 13, fontWeight: "700", writingDirection: "rtl" },
  headerActions: { alignItems: "center", minWidth: 48 },
  headerBuildButton: { borderColor: fiticianTokens.colors.aqua, borderRadius: 999, borderWidth: 1, minHeight: 44, justifyContent: "center", paddingHorizontal: 14 },
  headerBuildText: { color: fiticianTokens.colors.aqua, fontFamily: fiticianTokens.typography.fontFamily.bodyPersian, fontSize: 13, fontWeight: "800", writingDirection: "rtl" },
  menuButton: { alignItems: "center", borderColor: fiticianTokens.colors.line, borderRadius: 999, borderWidth: 1, gap: 5, height: 44, justifyContent: "center", width: 44 },
  menuLine: { backgroundColor: fiticianTokens.colors.mist, height: 2, width: 18 },
  menuLineShort: { backgroundColor: fiticianTokens.colors.mist, height: 2, width: 12 },
  menu: { backgroundColor: "rgba(6,21,19,0.98)", borderLeftColor: fiticianTokens.colors.line, borderLeftWidth: 1, bottom: 0, padding: 16, position: "absolute", right: 0, top: 0, width: "88%", zIndex: 30 },
  menuClose: { alignItems: "center", borderColor: fiticianTokens.colors.line, borderRadius: 999, borderWidth: 1, height: 44, justifyContent: "center", marginLeft: "auto", width: 44 },
  menuCloseText: { color: fiticianTokens.colors.mist, fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish, fontSize: 24, lineHeight: 28 },
  menuLinks: { marginTop: 32 },
  menuLink: { borderBottomColor: fiticianTokens.colors.line, borderBottomWidth: 1, minHeight: 56, justifyContent: "center", paddingHorizontal: 12 },
  menuLinkText: { color: fiticianTokens.colors.mist, fontFamily: fiticianTokens.typography.fontFamily.bodyPersian, fontSize: 16, fontWeight: "800", writingDirection: "rtl" },
  cinematicSection: { backgroundColor: landingBackground, position: "relative" },
  cinematicStage: { backgroundColor: landingBackground, left: 0, overflow: "hidden", position: "absolute", right: 0, top: 0 },
  reducedCinematicStage: { backgroundColor: landingBackground, left: 0, overflow: "visible", position: "relative", right: 0, top: 0 },
  cinematicScene: { bottom: 0, left: 0, paddingHorizontal: 20, position: "absolute", right: 0, top: 0 },
  reducedScene: { bottom: undefined, left: undefined, minHeight: 560, position: "relative", right: undefined, top: undefined },
  filmLayer: { bottom: 0, left: 0, overflow: "hidden", position: "absolute", right: 0, top: 0 },
  filmMediaLayer: { bottom: 0, left: 0, position: "absolute", right: 0, top: 0 },
  filmMedia: { bottom: 0, height: "100%", left: 0, position: "absolute", right: 0, top: 0, width: "100%" },
  cinematicShade: { backgroundColor: "rgba(2,11,12,0.48)", bottom: 0, left: 0, position: "absolute", right: 0, top: 0 },
  cinematicShadeCompact: { backgroundColor: "rgba(2,11,12,0.58)" },
  cinematicFade: { backgroundColor: landingBackground, bottom: 0, left: 0, position: "absolute", right: 0, top: 0 },
  cinematicSceneCompact: { paddingHorizontal: 16 },
  heroScene: { alignItems: "flex-start", justifyContent: "center", paddingTop: 76 },
  heroSceneCompact: { justifyContent: "flex-end", paddingBottom: 0, paddingTop: 0 },
  heroCopy: { maxWidth: 520, width: "100%" },
  heroTitle: { color: fiticianTokens.colors.mist, fontFamily: fiticianTokens.typography.fontFamily.displayPersian, fontSize: 54, lineHeight: 62, textAlign: "auto", textShadowColor: "rgba(0,0,0,0.55)", textShadowOffset: { height: 8, width: 0 }, textShadowRadius: 24, writingDirection: "rtl" },
  heroTitleCompact: { fontSize: 50, lineHeight: 52 },
  heroBody: { color: "rgba(232,244,241,0.75)", fontFamily: fiticianTokens.typography.fontFamily.bodyPersian, fontSize: 16, lineHeight: 29, marginTop: 18, maxWidth: 480, textAlign: "auto", writingDirection: "rtl" },
  heroBodyCompact: { fontSize: 15, lineHeight: 26, marginTop: 14 },
  cta: { alignSelf: "flex-start", marginTop: 22, minWidth: 168 },
  scrollIndicator: { alignSelf: "center", backgroundColor: "rgba(232,244,241,0.18)", bottom: 24, height: 56, overflow: "hidden", position: "absolute", width: 1 },
  scrollIndicatorFill: { backgroundColor: fiticianTokens.colors.aqua, height: "45%", width: 1 },
  supervisionScene: { alignItems: "center", flexDirection: "column", gap: 24, justifyContent: "center" },
  supervisionSceneWide: { flexDirection: "row", gap: 48 },
  supervisionSceneCompact: { gap: 18, paddingBottom: 16, paddingTop: 86 },
  sceneCopy: { maxWidth: 340, width: "100%" },
  sceneCopyCompact: { maxWidth: 300 },
  sceneEyebrow: { color: fiticianTokens.colors.aqua, fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish, fontSize: 12, fontWeight: "700", letterSpacing: 2.4, marginBottom: 14, textAlign: "left", writingDirection: "ltr" },
  sceneTitle: { color: fiticianTokens.colors.mist, fontFamily: fiticianTokens.typography.fontFamily.displayPersian, fontSize: 38, lineHeight: 46, textAlign: "auto", textShadowColor: "rgba(0,0,0,0.4)", textShadowOffset: { height: 8, width: 0 }, textShadowRadius: 18, writingDirection: "rtl" },
  sceneTitleCompact: { fontSize: 32, lineHeight: 36 },
  planPaper: { aspectRatio: 0.88, backgroundColor: "rgba(10,32,30,0.92)", borderColor: "rgba(205,239,232,0.12)", borderRadius: 22, borderWidth: 1, elevation: 6, minHeight: 0, padding: 24, shadowColor: "#000000", shadowOffset: { height: 12, width: 0 }, shadowOpacity: 0.28, shadowRadius: 24, width: "100%", maxWidth: 464 },
  planPaperCompact: { borderRadius: 16, padding: 22 },
  planPaperNutrition: { borderRadius: 18 },
  planPaperWide: { flex: 1 },
  planHeader: { alignItems: "center", borderBottomColor: "rgba(232,244,241,0.08)", borderBottomWidth: 1, flexDirection: "row", gap: 12, paddingBottom: 24 },
  planHeaderCompact: { gap: 8, paddingBottom: 16 },
  planAvatar: { backgroundColor: "rgba(80,223,206,0.16)", borderColor: "rgba(80,223,206,0.3)", borderRadius: 999, borderWidth: 1, height: 38, width: 38 },
  planAvatarCompact: { height: 32, width: 32 },
  planHeaderLine: { backgroundColor: "rgba(220,239,234,0.12)", borderRadius: 999, height: 8, width: "42%" },
  planContent: { gap: 22, paddingVertical: 28 },
  planContentCompact: { gap: 14, paddingVertical: 18 },
  planGroup: { borderBottomColor: "rgba(232,244,241,0.05)", borderBottomWidth: 1, gap: 8, paddingBottom: 18 },
  planGroupCompact: { gap: 6, paddingBottom: 12 },
  planLineWide: { backgroundColor: "rgba(220,239,234,0.12)", borderRadius: 999, height: 8, width: "84%" },
  planLineMedium: { backgroundColor: "rgba(220,239,234,0.08)", borderRadius: 999, height: 8, width: "62%" },
  planLineShort: { backgroundColor: "rgba(220,239,234,0.05)", borderRadius: 999, height: 8, width: "74%" },
  planGroupTiles: { flexDirection: "row", gap: 12 },
  planGroupTilesCompact: { gap: 8 },
  planTile: { backgroundColor: "rgba(80,223,206,0.06)", borderRadius: 8, flex: 1, height: 48 },
  planTileCompact: { height: 32 },
  verificationSeal: { alignItems: "center", backgroundColor: "rgba(4,18,17,0.96)", borderColor: "rgba(118,231,170,0.18)", borderRadius: 16, bottom: -26, gap: 5, padding: 10, position: "absolute", right: -12, width: 133 },
  verificationSealCompact: { bottom: -18, padding: 8, right: -18, width: 112 },
  verificationSealText: { color: "rgba(232,244,241,0.74)", fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish, fontSize: 8, textAlign: "center", writingDirection: "ltr" },
  mealScene: { alignItems: "center", flexDirection: "column", gap: 24, justifyContent: "center" },
  mealSceneWide: { flexDirection: "row", gap: 48 },
  mealSceneCompact: { gap: 16, paddingBottom: 24, paddingTop: 76 },
  sceneNote: { color: fiticianTokens.colors.muted, fontFamily: fiticianTokens.typography.fontFamily.bodyPersian, fontSize: 14, marginTop: 14, textAlign: "auto", writingDirection: "rtl" },
  mealVisual: { maxWidth: 360, position: "relative", width: "100%" },
  scanFrame: { aspectRatio: 0.92, backgroundColor: "#061817", borderColor: "rgba(232,244,241,0.1)", borderRadius: 24, borderWidth: 1, overflow: "hidden", position: "relative", width: "100%" },
  scanFrameMealCompact: { alignSelf: "center", aspectRatio: 0.86 },
  scanImage: { height: "100%", width: "100%" },
  scanCorner: { borderColor: fiticianTokens.colors.aqua, height: 36, position: "absolute", width: 36, zIndex: 3 },
  scanCornerOne: { borderLeftWidth: 2, borderTopLeftRadius: 10, borderTopWidth: 2, left: 16, top: 16 },
  scanCornerTwo: { borderRightWidth: 2, borderTopRightRadius: 10, borderTopWidth: 2, right: 16, top: 16 },
  scanCornerThree: { borderBottomLeftRadius: 10, borderBottomWidth: 2, borderLeftWidth: 2, bottom: 16, left: 16 },
  scanCornerFour: { borderBottomRightRadius: 10, borderBottomWidth: 2, borderRightWidth: 2, bottom: 16, right: 16 },
  scanLine: { backgroundColor: fiticianTokens.colors.aqua, height: 1, left: "6%", position: "absolute", right: "6%", shadowColor: fiticianTokens.colors.aqua, shadowOpacity: 0.72, shadowRadius: 12, zIndex: 4 },
  mealResult: { backgroundColor: "rgba(4,18,17,0.96)", borderColor: "rgba(80,223,206,0.2)", borderRadius: 16, borderWidth: 1, bottom: -22, elevation: 5, padding: 16, position: "absolute", right: 0, shadowColor: "#000000", shadowOpacity: 0.36, shadowRadius: 18, width: "88%" },
  mealResultCompact: { bottom: -16, padding: 14 },
  mealCalories: { color: fiticianTokens.colors.mist, fontFamily: fiticianTokens.typography.fontFamily.displayEnglish, fontSize: 34, fontWeight: "700", textAlign: "left", writingDirection: "ltr" },
  macroRow: { flexDirection: "row", gap: 8, marginTop: 12 },
  macro: { flex: 1, gap: 4 },
  macroLabel: { color: fiticianTokens.colors.aqua, fontFamily: fiticianTokens.typography.fontFamily.bodyPersian, fontSize: 10, textAlign: "auto", writingDirection: "rtl" },
  macroValue: { color: "rgba(232,244,241,0.76)", fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish, fontSize: 11, textAlign: "left", writingDirection: "ltr" },
  processSection: { backgroundColor: landingBackground, position: "relative" },
  processStage: { alignSelf: "center", justifyContent: "center", paddingHorizontal: 20, position: "absolute", right: 0, left: 0, top: 0 },
  processStageCompact: { justifyContent: "flex-start", paddingBottom: 32, paddingHorizontal: 12, paddingTop: 92 },
  reducedProcessStage: { padding: 20, position: "relative" },
  processHeader: { maxWidth: 600, width: "100%" },
  landingKicker: { color: fiticianTokens.colors.aqua, fontFamily: fiticianTokens.typography.fontFamily.bodyPersian, fontSize: 12, fontWeight: "700", letterSpacing: 1.2, marginBottom: 12, textAlign: "auto", writingDirection: "rtl" },
  processTitle: { color: fiticianTokens.colors.mist, fontFamily: fiticianTokens.typography.fontFamily.displayPersian, fontSize: 38, lineHeight: 46, textAlign: "auto", writingDirection: "rtl" },
  processTitleCompact: { fontSize: 34, lineHeight: 40 },
  processList: { marginTop: 28, maxWidth: 600, width: "100%" },
  processListCompact: { marginTop: 26 },
  processStep: { alignItems: "center", flexDirection: "row", minHeight: 92, paddingVertical: 10, position: "relative" },
  processStepCompact: { minHeight: 84, paddingVertical: 8 },
  progressRing: { alignItems: "center", height: 70, justifyContent: "center", width: 70 },
  progressRingCompact: { height: 64, width: 64 },
  progressRingNumber: { color: fiticianTokens.colors.aqua, fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish, fontSize: 12, fontWeight: "700", position: "absolute", writingDirection: "ltr" },
  processStepCopy: { flex: 1, gap: 4, marginLeft: 16 },
  processStepCopyCompact: { marginLeft: 14 },
  processStepEyebrow: { color: fiticianTokens.colors.muted, fontFamily: fiticianTokens.typography.fontFamily.bodyPersian, fontSize: 12, fontWeight: "700", textAlign: "auto", writingDirection: "rtl" },
  processStepTitle: { color: fiticianTokens.colors.mist, fontFamily: fiticianTokens.typography.fontFamily.bodyPersian, fontSize: 16, lineHeight: 25, textAlign: "auto", writingDirection: "rtl" },
  processStepTitleCompact: { fontSize: 15, lineHeight: 22 },
  processConnectorTrack: { backgroundColor: "rgba(232,244,241,0.12)", bottom: -24, height: 38, left: 34, overflow: "hidden", position: "absolute", width: 2 },
  processConnectorTrackCompact: { bottom: undefined, height: 24, left: 31, top: 64, width: 1 },
  processConnectorFill: { backgroundColor: fiticianTokens.colors.aqua, left: 0, position: "absolute", right: 0, top: 0 },
  bodySection: { backgroundColor: landingBackground, position: "relative" },
  bodyStage: { alignSelf: "center", paddingHorizontal: 20, position: "absolute", right: 0, left: 0, top: 0 },
  reducedBodyStage: { padding: 20, position: "relative" },
  bodyStageCompact: { paddingHorizontal: 12 },
  bodyHeading: { maxWidth: 560, paddingTop: 96, width: "100%" },
  bodyHeadingCompact: { paddingTop: 84 },
  bodyTitle: { color: fiticianTokens.colors.mist, fontFamily: fiticianTokens.typography.fontFamily.displayPersian, fontSize: 38, lineHeight: 46, textAlign: "auto", writingDirection: "rtl" },
  bodyTitleCompact: { fontSize: 34, lineHeight: 38 },
  bodyDescription: { color: fiticianTokens.colors.muted, fontFamily: fiticianTokens.typography.fontFamily.bodyPersian, fontSize: 14, lineHeight: 25, marginTop: 12, textAlign: "auto", writingDirection: "rtl" },
  bodyDescriptionCompact: { fontSize: 13, lineHeight: 22, marginTop: 9 },
  bodyCapture: { alignSelf: "center", gap: 8, maxWidth: 384, position: "absolute", top: "34%", width: "100%" },
  bodyCaptureCompact: { gap: 6 },
  bodyCaptureWide: { alignSelf: "flex-start", left: 20 },
  bodyScanFrame: { aspectRatio: 0.68, backgroundColor: "#061817", borderColor: "rgba(232,244,241,0.1)", borderRadius: 24, borderWidth: 1, overflow: "hidden", position: "relative", width: "100%" },
  bodyScanFrameCompact: { alignSelf: "center", aspectRatio: 0.68 },
  bodyCaptureImage: { height: "100%", width: "100%" },
  bodyCaptureLabel: { color: fiticianTokens.colors.muted, fontFamily: fiticianTokens.typography.fontFamily.bodyPersian, fontSize: 12, textAlign: "center", writingDirection: "rtl" },
  bodyInterface: { alignSelf: "center", aspectRatio: 2 / 3, borderColor: "rgba(232,244,241,0.1)", borderRadius: 24, borderWidth: 1, maxWidth: 340, overflow: "hidden", position: "absolute", top: "29%", width: "100%" },
  bodyInterfaceCompact: { top: "29%", width: "100%" },
  bodyInterfaceWide: { alignSelf: "flex-end", right: 20, top: "22%" },
  bodyInterfaceImage: { height: "100%", width: "100%" },
  bodyMuscles: { bottom: 0, height: "100%", left: 0, position: "absolute", right: 0, top: 0, width: "100%" },
  bodyConnectors: { bottom: 0, height: "100%", left: 0, position: "absolute", right: 0, top: 0, width: "100%" },
  bodyHotspot: { alignItems: "center", backgroundColor: "transparent", borderColor: fiticianTokens.colors.aqua, borderRadius: 999, borderWidth: 1, height: 46, justifyContent: "center", padding: 0, position: "absolute", width: 46 },
  bodyHotspotActive: { opacity: 1 },
  bodyHotspotInactive: { opacity: 0.2 },
  shoulderHotspot: { right: "23%", top: "21%" },
  backHotspot: { right: "46%", top: "36%" },
  hotspotDot: { backgroundColor: fiticianTokens.colors.aqua, borderRadius: 999, height: 9, shadowColor: fiticianTokens.colors.aqua, shadowOpacity: 0.9, shadowRadius: 10, width: 9 },
  bodyMapping: { bottom: 0, left: 0, position: "absolute", right: 0, top: 0 },
  bodyMappingDot: { backgroundColor: fiticianTokens.colors.aqua, borderRadius: 999, height: 8, shadowColor: fiticianTokens.colors.aqua, shadowOpacity: 0.9, shadowRadius: 10, width: 8 },
  bodyMappingOne: { left: "31%", position: "absolute", top: "36%" },
  bodyMappingTwo: { position: "absolute", right: "31%", top: "36%" },
  bodyMappingThree: { position: "absolute", right: "49%", top: "53%" },
  bodyCallout: { backgroundColor: "rgba(4,18,17,0.94)", borderColor: fiticianTokens.colors.lineStrong, borderRadius: 14, borderWidth: 1, gap: 4, minWidth: 152, paddingHorizontal: 12, paddingVertical: 10, position: "absolute", right: 0, top: "17%" },
  bodyCalloutCompact: { minWidth: 131, paddingHorizontal: 13, paddingVertical: 11, top: "13%" },
  bodyCalloutBack: { top: "46%" },
  bodyCalloutBackCompact: { top: "45%" },
  bodyCalloutLabel: { color: fiticianTokens.colors.muted, fontFamily: fiticianTokens.typography.fontFamily.bodyPersian, fontSize: 11, textAlign: "auto", writingDirection: "rtl" },
  bodyCalloutValue: { color: fiticianTokens.colors.mist, fontFamily: fiticianTokens.typography.fontFamily.bodyPersian, fontSize: 14, fontWeight: "700", textAlign: "auto", writingDirection: "rtl" },
  finalSection: { alignItems: "center", backgroundColor: landingBackground, borderTopColor: "rgba(232,244,241,0.06)", borderTopWidth: 1, justifyContent: "center", padding: 20 },
  finalTitle: { color: fiticianTokens.colors.mist, fontFamily: fiticianTokens.typography.fontFamily.displayPersian, fontSize: 38, lineHeight: 46, textAlign: "center", writingDirection: "rtl" },
});
