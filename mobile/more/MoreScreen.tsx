import { useRouter } from "expo-router";
import { StyleSheet, Text, View } from "react-native";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { AppIcon, Card, ScreenHeader, SectionHeader } from "../ui/components";
import { useMobileRouteSnapshot } from "../ui/navigation/RouteGuards";
import { decideMobileRoute, type MobileRouteSnapshot } from "../ui/navigation/routePolicy";
import { Screen } from "../ui/layout";
import { fiticianTokens } from "../ui/tokens";

type MoreDestination = {
  readonly icon: "calendar" | "foodLog" | "training";
  readonly path: "/member/exercises" | "/member/food-catalogue" | "/member/meal-catalogue";
  readonly subtitle: string;
  readonly title: string;
};

export function MoreScreen() {
  const auth = useMobileAuth();
  const router = useRouter();
  const snapshot = useMobileRouteSnapshot();
  const destinations = getMoreDestinations(snapshot);
  const accountContact = auth.user?.email?.trim() || auth.user?.phone_number?.trim() || null;

  return (
    <Screen contentWidth="reading" contentContainerStyle={styles.screen}>
      <ScreenHeader
        compact
        eyebrow="فضای تو"
        subtitle="پروفایل و کتابخانه‌ها در یکجا."
        title="بیشتر"
      />

      <Card
        accessibilityLabel="پروفایل من"
        onPress={() => router.push("/member/profile")}
        style={styles.profileCard}
        variant="hero"
      >
        <View style={styles.profileRow}>
          <View style={styles.profileIcon}>
            <AppIcon color={fiticianTokens.colors.aqua} name="profile" size={fiticianTokens.iconSize.xl} />
          </View>
          <View style={styles.profileCopy}>
            <Text style={styles.profileTitle}>پروفایل من</Text>
            <Text style={styles.profileSubtitle}>مشخصات و تنظیمات شخصی</Text>
            {accountContact ? <Text numberOfLines={1} style={styles.accountContact}>{accountContact}</Text> : null}
          </View>
          <AppIcon color={fiticianTokens.colors.aqua} name="arrowLeft" size={fiticianTokens.iconSize.md} />
        </View>
      </Card>

      {destinations.length > 0 ? (
        <View style={styles.libraryGroup}>
          <SectionHeader eyebrow="دسترسی آسان" title="کتابخانه‌ها" />
          <View style={styles.destinationStack}>
            {destinations.map((destination) => (
              <Card
                accessibilityLabel={destination.title}
                key={destination.path}
                onPress={() => router.push(destination.path)}
                style={styles.destinationCard}
                variant="default"
              >
                <View style={styles.destinationRow}>
                  <View style={styles.destinationIcon}>
                    <AppIcon color={fiticianTokens.colors.aqua} name={destination.icon} size={fiticianTokens.iconSize.lg} />
                  </View>
                  <View style={styles.destinationCopy}>
                    <Text style={styles.destinationTitle}>{destination.title}</Text>
                    <Text style={styles.destinationSubtitle}>{destination.subtitle}</Text>
                  </View>
                  <AppIcon color={fiticianTokens.colors.muted} name="arrowLeft" size={fiticianTokens.iconSize.md} />
                </View>
              </Card>
            ))}
          </View>
        </View>
      ) : null}
    </Screen>
  );
}

function getMoreDestinations(snapshot: MobileRouteSnapshot): readonly MoreDestination[] {
  const destinations: MoreDestination[] = [];
  if (canAccess(snapshot, "training")) {
    destinations.push({
      icon: "training",
      path: "/member/exercises",
      subtitle: "حرکت‌ها، نحوه اجرا و نکات تمرینی",
      title: "کتابخانه حرکات",
    });
  }
  if (canAccess(snapshot, "nutrition")) {
    destinations.push(
      {
        icon: "foodLog",
        path: "/member/food-catalogue",
        subtitle: "اطلاعات و ارزش غذایی مواد",
        title: "کتابخانه مواد غذایی",
      },
      {
        icon: "calendar",
        path: "/member/meal-catalogue",
        subtitle: "وعده‌ها و ترکیبات غذایی",
        title: "وعده‌های غذایی",
      },
    );
  }
  return destinations;
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
  destinationCard: {
    padding: fiticianTokens.spacing[4],
  },
  destinationCopy: {
    alignItems: "flex-end",
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  destinationIcon: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderRadius: fiticianTokens.radii.medium,
    height: 52,
    justifyContent: "center",
    width: 52,
  },
  destinationRow: {
    alignItems: "center",
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
  },
  destinationStack: {
    gap: fiticianTokens.spacing[3],
  },
  destinationSubtitle: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 22,
    textAlign: "right",
    writingDirection: "rtl",
  },
  destinationTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  libraryGroup: {
    gap: fiticianTokens.spacing[3],
  },
  profileCard: {
    padding: fiticianTokens.spacing[5],
  },
  profileCopy: {
    alignItems: "flex-end",
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  profileIcon: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderRadius: fiticianTokens.radii.pill,
    height: 60,
    justifyContent: "center",
    width: 60,
  },
  profileRow: {
    alignItems: "center",
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
  },
  profileSubtitle: {
    color: fiticianTokens.colors.mist,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 22,
    textAlign: "right",
    writingDirection: "rtl",
  },
  profileTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 28,
    textAlign: "right",
    writingDirection: "rtl",
  },
  screen: {
    gap: fiticianTokens.spacing[5],
    paddingBottom: fiticianTokens.spacing[7],
    paddingTop: fiticianTokens.spacing[3],
  },
});
