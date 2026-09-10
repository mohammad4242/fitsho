import { useEffect, useMemo, useState } from "react";
import { Linking, Image, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { AppIcon, Button, Card, GroupedList, Notice, PageHeading } from "../ui/components";
import type { GroupedListItem, GroupedListSection } from "../ui/components";
import { getMobileRuntimeConfig } from "../config/nativeRuntimeConfig";
import { createProfileApi } from "../profile/profileApi";
import { useMobileRouteSnapshot } from "../ui/navigation/RouteGuards";
import { decideMobileRoute, type MobileRouteSnapshot } from "../ui/navigation/routePolicy";
import { Screen } from "../ui/layout";
import { fiticianTokens } from "../ui/tokens";
import type { SharedProfile } from "@fitician/core/profile";

type MoreDestination = {
  readonly icon: "bodyAnalysis" | "calendar" | "foodLog" | "profile" | "shield" | "target" | "training";
  readonly path: "/member/body-analysis-history" | "/member/exercises" | "/member/food-catalogue" | "/member/meal-catalogue" | "/member/nutrition-tracking";
  readonly subtitle: string;
  readonly title: string;
};

type MoreRow = Pick<MoreDestination, "icon" | "subtitle" | "title"> & {
  readonly onPress: () => void;
};

export function MoreScreen() {
  const auth = useMobileAuth();
  const router = useRouter();
  const snapshot = useMobileRouteSnapshot();
  const profileApi = useMemo(() => createProfileApi(auth.request), [auth.request]);
  const [sharedProfile, setSharedProfile] = useState<SharedProfile | null | undefined>(undefined);
  const [logoutBusy, setLogoutBusy] = useState(false);
  const [logoutError, setLogoutError] = useState(false);
  const accountContact = auth.user?.email?.trim() || auth.user?.phone_number?.trim() || null;
  const accountLabel = sharedProfile?.display_name?.trim()
    || auth.user?.email?.trim()
    || auth.user?.phone_number?.trim()
    || "کاربر فیتشو";
  const profilePhotoUrl = sharedProfile?.profile_photo_url ?? auth.user?.profile_photo_url ?? null;

  useEffect(() => {
    let active = true;
    if (auth.user?.id === undefined) {
      setSharedProfile(null);
      return () => {
        active = false;
      };
    }
    void profileApi.getSharedProfile()
      .then((profile) => {
        if (active) setSharedProfile(profile);
      })
      .catch(() => {
        if (active) setSharedProfile(null);
      });
    return () => {
      active = false;
    };
  }, [auth.user?.id, profileApi]);

  const productItems = getProductItems(snapshot, router);
  const workspaceItems = getWorkspaceItems(snapshot, router);
  const sections: GroupedListSection[] = [
    ...(productItems.length > 0 ? [{ items: productItems, title: "محصول" }] : []),
    {
      items: [
        moreItem({
          icon: "profile",
          onPress: () => router.push("/member/profile"),
          subtitle: "مشخصات و تنظیمات برنامه",
          title: "اطلاعات پروفایل",
        }),
        moreItem({
          icon: "profile",
          onPress: () => router.push("/account-deletion"),
          subtitle: "مدیریت درخواست حذف حساب",
          title: "حذف حساب",
        }),
        moreItem({
          icon: "shield",
          onPress: openPrivacyPolicy,
          subtitle: "نحوه استفاده و کنترل داده‌ها",
          title: "سیاست حریم خصوصی",
        }),
      ],
      title: "حساب و حریم خصوصی",
    },
    ...(workspaceItems.length > 0 ? [{ items: workspaceItems, title: "فضاهای تخصصی" }] : []),
  ];

  async function handleLogout() {
    if (logoutBusy) return;
    setLogoutBusy(true);
    setLogoutError(false);
    try {
      await auth.logout();
      router.replace("/auth/sign-in");
    } catch {
      setLogoutError(true);
    } finally {
      setLogoutBusy(false);
    }
  }

  function openPrivacyPolicy() {
    const runtime = getMobileRuntimeConfig();
    void Linking.openURL(`${runtime.frontendOrigin}/privacy`).catch(() => undefined);
  }

  return (
    <Screen contentWidth="reading" contentContainerStyle={styles.screen}>
      <PageHeading title="بیشتر" />

      <Card
        accessibilityLabel="پروفایل من"
        onPress={() => router.push("/member/profile")}
        style={styles.profileCard}
        variant="raised"
      >
        <View style={styles.profileRow}>
          {profilePhotoUrl ? (
            <Image accessibilityLabel={accountLabel} source={{ uri: profilePhotoUrl }} style={styles.profileAvatar} />
          ) : (
            <View style={styles.profileAvatarFallback}>
              <Text style={styles.profileAvatarText}>{accountLabel.slice(0, 1) || "ف"}</Text>
            </View>
          )}
          <View style={styles.profileCopy}>
            <Text style={styles.profileTitle}>{accountLabel}</Text>
            <Text style={styles.profileSubtitle}>مشخصات و تنظیمات شخصی</Text>
            {accountContact ? <Text numberOfLines={1} style={styles.accountContact}>{accountContact}</Text> : null}
          </View>
          <AppIcon color={fiticianTokens.colors.aqua} name="arrowLeft" size={fiticianTokens.iconSize.md} />
        </View>
      </Card>

      <GroupedList sections={sections} testID="more-groups" />
      {logoutError ? <Notice message="خروج از حساب انجام نشد. دوباره تلاش کن." variant="danger" /> : null}
      <Button disabled={logoutBusy} label="خروج از حساب" loading={logoutBusy} onPress={() => void handleLogout()} style={styles.logout} variant="danger" />
    </Screen>
  );
}

function getProductItems(snapshot: MobileRouteSnapshot, router: ReturnType<typeof useRouter>): readonly GroupedListItem[] {
  const destinations: MoreDestination[] = [];
  if (canAccess(snapshot, "training")) {
    destinations.push(
      {
        icon: "training",
        path: "/member/exercises",
        subtitle: "حرکت‌ها، نحوه اجرا و نکات ایمنی",
        title: "کتابخانه حرکات",
      },
      {
        icon: "bodyAnalysis",
        path: "/member/body-analysis-history",
        subtitle: "جلسه‌ها و تحلیل‌های ثبت‌شده",
        title: "تحلیل بدن",
      },
    );
  }
  if (canAccess(snapshot, "nutrition")) {
    destinations.push(
      {
        icon: "foodLog",
        path: "/member/food-catalogue",
        subtitle: "مرجع سریع ارزش غذایی",
        title: "کاتالوگ مواد غذایی",
      },
      {
        icon: "calendar",
        path: "/member/meal-catalogue",
        subtitle: "وعده‌ها و ترکیبات غذایی",
        title: "کاتالوگ وعده‌های غذایی",
      },
      {
        icon: "target",
        path: "/member/nutrition-tracking",
        subtitle: "پیگیری ساده وضعیت روز",
        title: "ثبت تغذیه",
      },
    );
  }
  return destinations.map((destination) => ({
    icon: destination.icon,
    label: destination.title,
    onPress: () => router.push(destination.path),
    subtitle: destination.subtitle,
    trailing: <AppIcon color={fiticianTokens.colors.muted} name="arrowLeft" size={fiticianTokens.iconSize.md} />,
  }));
}

function getWorkspaceItems(snapshot: MobileRouteSnapshot, router: ReturnType<typeof useRouter>): readonly GroupedListItem[] {
  const workspaces: GroupedListItem[] = [];
  if (snapshot.specialistAccess.coach === "granted") {
    workspaces.push(moreItem({
      icon: "profile",
      onPress: () => router.push("/coach"),
      subtitle: "بازبینی و مدیریت برنامه‌های تمرینی",
      title: "فضای مربی",
    }));
  }
  if (snapshot.specialistAccess.physician === "granted") {
    workspaces.push(moreItem({
      icon: "profile",
      onPress: () => router.push("/physician"),
      subtitle: "بازبینی و مدیریت برنامه‌های تغذیه‌ای",
      title: "فضای پزشک",
    }));
  }
  return workspaces;
}

function moreItem({
  icon,
  onPress,
  subtitle,
  title,
}: MoreRow): GroupedListItem {
  return {
    icon,
    label: title,
    onPress,
    subtitle,
    trailing: <AppIcon color={fiticianTokens.colors.muted} name="arrowLeft" size={fiticianTokens.iconSize.md} />,
  };
}

function canAccess(snapshot: MobileRouteSnapshot, capability: "training" | "nutrition"): boolean {
  return decideMobileRoute("member", snapshot, capability).status === "allow";
}

const styles = StyleSheet.create({
  accountContact: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    maxWidth: "100%",
    textAlign: "right",
    writingDirection: "ltr",
  },
  logout: {
    width: "100%",
  },
  profileCard: {
    padding: fiticianTokens.spacing[4],
  },
  profileAvatar: {
    backgroundColor: fiticianTokens.colors.surfaceRaised,
    borderRadius: fiticianTokens.radii.pill,
    height: 48,
    width: 48,
  },
  profileAvatarFallback: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.aqua,
    borderRadius: fiticianTokens.radii.pill,
    height: 48,
    justifyContent: "center",
    width: 48,
  },
  profileAvatarText: {
    color: fiticianTokens.colors.canvas,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
  },
  profileCopy: {
    alignItems: "stretch",
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  profileRow: {
    alignItems: "center",
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
  },
  profileSubtitle: {
    color: fiticianTokens.colors.mist,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 22,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  profileTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 28,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  screen: {
    gap: fiticianTokens.spacing[5],
    paddingBottom: fiticianTokens.spacing[7],
    paddingTop: fiticianTokens.spacing[3],
  },
});
