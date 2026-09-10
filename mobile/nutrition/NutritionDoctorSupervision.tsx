import { useRouter } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { AppIcon, DisclosureCard } from "../ui/components";
import { fiticianTokens } from "../ui/tokens";
import type { WeeklyPlan } from "./nutritionPlanApi";

const pendingStatuses = new Set([
  "pending",
  "pending_physician_review",
  "physician_review_in_progress",
  "awaiting_lab_information",
]);

export function NutritionDoctorSupervision({ plan }: { readonly plan: WeeklyPlan | null }) {
  const router = useRouter();
  const isPending = plan !== null
    && !plan.physician_approved
    && (pendingStatuses.has(plan.review_status) || pendingStatuses.has(plan.lifecycle_status));
  const isApproved = plan?.physician_approved === true
    || ["physician_approved", "active"].includes(plan?.lifecycle_status ?? "");
  const approvalCopy = plan === null
    ? "پس از ساخت برنامه"
    : isPending
      ? "در انتظار تأیید پزشک"
      : isApproved
        ? "تأییدشده توسط پزشک"
        : "نیازمند بررسی";
  const guidanceCopy = plan?.physician_user_visible_notes
    ?? (isPending ? "پس از بررسی پزشک" : "راهنمایی ثبت نشده");

  return (
    <DisclosureCard
      leading={<View style={styles.doctorIcon}><AppIcon color={fiticianTokens.colors.aqua} name="doctor" size={fiticianTokens.iconSize.lg} /></View>}
      style={styles.card}
      summary="خدمات و وضعیت بررسی پزشکی در یک نگاه"
      title="تحت نظر پزشک"
      trailing={isPending ? <Text style={styles.pendingHeader}>● در انتظار پزشک</Text> : null}
    >
      <View style={styles.itemGrid}>
        <DoctorItem
          icon="supplement"
          label="مکمل‌های من"
          onPress={() => router.push("/member/nutrition-supplements")}
          subtitle="دستورها و پیگیری مکمل‌ها"
          tag="تجویز و پیگیری"
          variant="supplements"
        />
        <DoctorItem
          icon="check"
          label="تأیید برنامه غذایی"
          pending={isPending}
          subtitle={approvalCopy}
          variant="approved"
        />
        <DoctorItem
          icon="lab"
          label="آزمایشات من"
          onPress={() => router.push("/member/nutrition-labs")}
          subtitle="نتایج و سابقه بررسی"
          variant="labs"
        />
        <DoctorItem
          icon="document"
          label="راهنمایی‌های پزشک"
          subtitle={guidanceCopy}
          variant="guidance"
        />
      </View>
    </DisclosureCard>
  );
}

function DoctorItem({
  icon,
  label,
  onPress,
  pending = false,
  subtitle,
  tag,
  variant,
}: {
  readonly icon: "check" | "document" | "lab" | "supplement";
  readonly label: string;
  readonly onPress?: () => void;
  readonly pending?: boolean;
  readonly subtitle: string;
  readonly tag?: string;
  readonly variant: "approved" | "guidance" | "labs" | "supplements";
}) {
  const content = (
    <>
      <View style={[styles.itemIcon, styles[`itemIcon_${variant}`]]}>
        <AppIcon color={variant === "guidance" ? fiticianTokens.colors.amber : fiticianTokens.colors.aqua} name={icon} size={fiticianTokens.iconSize.md} />
      </View>
      <View style={styles.itemCopy}>
        <View style={styles.itemTitleRow}>
          <Text style={styles.itemTitle}>{label}</Text>
          {tag ? <Text style={styles.itemTag}>{tag}</Text> : null}
        </View>
        <Text style={[styles.itemSubtitle, pending && styles.pendingSubtitle]}>
          {pending ? "● " : ""}{subtitle}
        </Text>
      </View>
      {onPress ? <AppIcon color={fiticianTokens.colors.muted} name="arrowLeft" size={fiticianTokens.iconSize.sm} /> : null}
    </>
  );

  if (onPress) {
    return (
      <Pressable
        accessibilityLabel={label}
        accessibilityRole="button"
        onPress={onPress}
        style={({ pressed }) => [styles.item, pressed && styles.pressed]}
      >
        {content}
      </Pressable>
    );
  }
  return <View style={styles.item}>{content}</View>;
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: "rgba(9, 54, 51, 0.45)",
    borderColor: fiticianTokens.colors.line,
    marginBottom: fiticianTokens.spacing[1],
    padding: 0,
  },
  doctorIcon: {
    alignItems: "center",
    backgroundColor: "rgba(80, 223, 206, 0.14)",
    borderColor: "rgba(80, 223, 206, 0.3)",
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    height: 44,
    justifyContent: "center",
    width: 44,
  },
  item: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
    minHeight: 72,
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[3],
  },
  itemCopy: {
    flex: 1,
    gap: fiticianTokens.spacing[1],
    minWidth: 0,
  },
  itemGrid: {
    gap: fiticianTokens.spacing[2],
  },
  itemIcon: {
    alignItems: "center",
    borderRadius: fiticianTokens.radii.small,
    borderWidth: 1,
    height: 38,
    justifyContent: "center",
    width: 38,
  },
  itemIcon_approved: {
    backgroundColor: "rgba(102, 200, 159, 0.15)",
    borderColor: "rgba(102, 200, 159, 0.35)",
  },
  itemIcon_guidance: {
    backgroundColor: "rgba(242, 184, 91, 0.15)",
    borderColor: "rgba(242, 184, 91, 0.35)",
  },
  itemIcon_labs: {
    backgroundColor: "rgba(150, 160, 255, 0.15)",
    borderColor: "rgba(150, 160, 255, 0.35)",
  },
  itemIcon_supplements: {
    backgroundColor: "rgba(80, 223, 206, 0.12)",
    borderColor: "rgba(80, 223, 206, 0.3)",
  },
  itemTag: {
    backgroundColor: "rgba(80, 223, 206, 0.14)",
    borderColor: "rgba(80, 223, 206, 0.3)",
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 9,
    paddingHorizontal: fiticianTokens.spacing[2],
    paddingVertical: 1,
    textAlign: "center",
    writingDirection: "rtl",
  },
  itemTitle: {
    color: fiticianTokens.colors.ink,
    flexShrink: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  itemTitleRow: {
    alignItems: "center",
    flexDirection: "row",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
  itemSubtitle: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 20,
    textAlign: "right",
    writingDirection: "rtl",
  },
  pendingHeader: {
    color: fiticianTokens.colors.danger,
    flexShrink: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 10,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  pendingSubtitle: {
    color: fiticianTokens.colors.danger,
  },
  pressed: {
    opacity: 0.82,
  },
});
