import { useQuery } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View, useWindowDimensions } from "react-native";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { profileKeys, workoutKeys, nutritionKeys } from "../data/queryKeys";
import { connectivityMonitor, type ConnectivityStatus } from "../platform/connectivity";
import { createProfileApi } from "../profile/profileApi";
import { createNutritionApi } from "../nutrition/nutritionApi";
import { createNutritionPlanApi } from "../nutrition/nutritionPlanApi";
import { createNutritionTrackingApi } from "../nutrition/nutritionTrackingApi";
import { createWorkoutPlanApi } from "../workouts/workoutApi";
import { getMobileViewState, type MobileViewState } from "../ui/requestState";
import { Notice, PageHeading } from "../ui/components";
import { Screen } from "../ui/layout";
import { fiticianTokens } from "../ui/tokens";
import { useMobileRouteSnapshot } from "../ui/navigation/RouteGuards";
import { NutritionSummaryCard } from "./NutritionSummaryCard";
import { QuickActionCard } from "./QuickActionCard";
import { currentWorkoutDay, nutritionSummary } from "./homeModel";
import { getQuickActionColumns } from "./homePresentation";
import { WorkoutTodayCard, type WorkoutHomeState } from "./WorkoutTodayCard";

const homeBodyImage = require("../assets/home-body.webp") as number;
const homeFoodImage = require("../assets/home-food.webp") as number;

export function MemberHomeScreen() {
  const auth = useMobileAuth();
  const { width } = useWindowDimensions();
  const router = useRouter();
  const snapshot = useMobileRouteSnapshot();
  const connectivityStatus = useConnectivityStatus();
  const profileApi = useMemo(() => createProfileApi(auth.request), [auth.request]);
  const workoutApi = useMemo(
    () => createWorkoutPlanApi(auth.request, auth.download),
    [auth.download, auth.request],
  );
  const nutritionApi = useMemo(() => createNutritionApi(auth.request), [auth.request]);
  const nutritionPlanApi = useMemo(
    () => createNutritionPlanApi(auth.request, auth.download),
    [auth.download, auth.request],
  );
  const nutritionTrackingApi = useMemo(
    () => createNutritionTrackingApi(auth.request, auth.download),
    [auth.download, auth.request],
  );
  const productMode = snapshot.profile.productMode;
  const hasTraining = productMode === null || productMode === "training" || productMode === "both";
  const hasNutrition = productMode === "nutrition" || productMode === "both";
  const today = new Date().toISOString().slice(0, 10);

  const sharedProfileQuery = useQuery({
    enabled: auth.status === "signed_in",
    queryFn: profileApi.getSharedProfile,
    queryKey: profileKeys.current(),
  });
  const workoutQuery = useQuery({
    enabled: hasTraining,
    queryFn: workoutApi.getActive,
    queryKey: workoutKeys.plan("active"),
  });
  const nutritionPlanQuery = useQuery({
    enabled: hasNutrition,
    queryFn: nutritionPlanApi.getLatest,
    queryKey: nutritionKeys.plan("latest"),
  });
  const nutritionEstimateQuery = useQuery({
    enabled: hasNutrition,
    queryFn: nutritionApi.getCurrentEstimate,
    queryKey: nutritionKeys.estimate(),
  });
  const trackingQuery = useQuery({
    enabled: hasNutrition,
    queryFn: () => nutritionTrackingApi.getDailyTracking(today),
    queryKey: nutritionKeys.tracking(today),
  });

  const workoutViewState = getMobileViewState(workoutQuery, {
    connectivityStatus,
    isEmpty: (data) => data === null,
  });
  const nutritionPlanState = getMobileViewState(nutritionPlanQuery, {
    connectivityStatus,
    isEmpty: (data) => data === null,
  });
  const nutritionEstimateState = getMobileViewState(nutritionEstimateQuery, {
    connectivityStatus,
    isEmpty: (data) => data === null,
  });
  const trackingState = getMobileViewState(trackingQuery, { connectivityStatus });
  const workoutPlan = viewData(workoutViewState);
  const nutritionPlan = viewData(nutritionPlanState);
  const nutritionEstimate = viewData(nutritionEstimateState);
  const tracking = viewData(trackingState);
  const nutritionDataLoading = hasNutrition && (
    nutritionPlanState.status === "loading"
    || nutritionEstimateState.status === "loading"
    || trackingState.status === "loading"
  );
  const nutritionHasError = [nutritionPlanState, nutritionEstimateState, trackingState]
    .some((state) => state.status === "error");
  const summary = nutritionSummary(nutritionPlan, nutritionEstimate, tracking, today);
  const workoutState = resolveWorkoutState(workoutViewState);
  const displayName = sharedProfileQuery.data?.display_name?.trim()
    || snapshot.session.user?.email?.split("@", 1)[0]
    || "دوست";
  const avatar = displayName.slice(0, 1).toLocaleUpperCase("fa-IR");

  return (
    <Screen contentWidth="reading" contentContainerStyle={styles.screen}>
      <PageHeading
        action={<Pressable
          accessibilityLabel="باز کردن پروفایل"
          accessibilityRole="button"
          onPress={() => router.push("/member/profile")}
          style={({ pressed }) => [styles.avatar, pressed && styles.pressed]}
        >
          <Text style={styles.avatarText}>{avatar}</Text>
        </Pressable>}
        supportingText="برای امروز آماده‌ای؟"
        title={`سلام، ${displayName}`}
      />

      {sharedProfileQuery.isError ? (
        <Notice message="نام پروفایل خوانده نشد؛ اطلاعاتت همچنان در دسترس است." variant="info" />
      ) : null}

      {hasTraining ? (
        <View style={styles.section}>
          <WorkoutTodayCard day={currentWorkoutDay(workoutPlan)} state={workoutState} />
        </View>
      ) : null}

      {hasNutrition ? (
        <View style={styles.section}>
          <NutritionSummaryCard
            error={nutritionHasError}
            loading={nutritionDataLoading}
            summary={summary}
          />
        </View>
      ) : null}

      <View style={[styles.quickGrid, getQuickActionColumns(width) === 1 && styles.quickGridStacked]}>
        <QuickActionCard
          icon="bodyAnalysis"
          image={homeBodyImage}
          onPress={() => router.push("/member/body-analysis-capture")}
          subtitle="پیشرفت بدنت را بهتر بشناس"
          title="تحلیل بدن"
        />
        {hasNutrition ? (
          <QuickActionCard
            icon="foodLog"
            image={homeFoodImage}
            onPress={() => router.push("/member/nutrition-tracking")}
            subtitle="وعده امروزت را ثبت کن"
            title="ثبت غذا"
          />
        ) : null}
      </View>

      {hasTraining && workoutState === "error" ? (
        <Text style={styles.supportingText}>برای تلاش دوباره، بخش تمرین را باز کن.</Text>
      ) : null}
      {hasTraining && workoutState === "offline" ? (
        <Text style={styles.offlineText}>اتصال اینترنت برقرار نیست؛ داده‌های ذخیره‌شده را می‌بینی.</Text>
      ) : null}
    </Screen>
  );
}

function resolveWorkoutState(state: MobileViewState<Awaited<ReturnType<ReturnType<typeof createWorkoutPlanApi>["getActive"]>>>): WorkoutHomeState {
  if (state.status === "loading") return "loading";
  if (state.status === "error") return "error";
  if (state.status === "offline") return "offline";
  if (state.status === "stale") return "stale";
  if (state.status === "empty") return "empty";
  return "ready";
}

function viewData<TData>(state: MobileViewState<TData>): TData | undefined {
  if (state.status === "loading") return undefined;
  return "data" in state ? state.data : undefined;
}

function useConnectivityStatus(): ConnectivityStatus {
  const [status, setStatus] = useState<ConnectivityStatus>(connectivityMonitor.getSnapshot().status);
  useEffect(() => connectivityMonitor.subscribe((snapshot) => setStatus(snapshot.status)), []);
  return status;
}

const styles = StyleSheet.create({
  avatar: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.aqua,
    borderRadius: fiticianTokens.radii.pill,
    height: fiticianTokens.layout.minimumTouchTarget,
    justifyContent: "center",
    width: fiticianTokens.layout.minimumTouchTarget,
  },
  avatarText: {
    color: fiticianTokens.colors.canvas,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    writingDirection: "rtl",
  },
  offlineText: {
    color: fiticianTokens.colors.amber,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.compact,
    lineHeight: 20,
    textAlign: "right",
    writingDirection: "rtl",
  },
  pressed: {
    opacity: 0.82,
    transform: [{ scale: fiticianTokens.motion.pressedScale }],
  },
  quickGrid: {
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
  },
  quickGridStacked: {
    flexDirection: "column",
  },
  screen: {
    gap: fiticianTokens.spacing[4],
    paddingBottom: fiticianTokens.spacing[7],
    paddingTop: fiticianTokens.spacing[3],
  },
  section: {
    gap: fiticianTokens.spacing[3],
  },
  supportingText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.compact,
    textAlign: "right",
    writingDirection: "rtl",
  },
});
