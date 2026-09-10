import { useRouter } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { AppIcon, DisclosureCard } from "../ui/components";
import { fiticianTokens } from "../ui/tokens";
import type { NutritionEstimate } from "./nutritionApi";

const micronutrientLabels: Readonly<Record<string, string>> = {
  calcium_mg: "کلسیم",
  folate_mcg_dfe: "فولات",
  iron_mg: "آهن",
  magnesium_mg: "منیزیم",
  potassium_mg: "پتاسیم",
  vitamin_b12_mcg: "ویتامین B12",
  vitamin_d_mcg: "ویتامین D",
  zinc_mg: "روی",
};

export function NutritionScienceDetails({ estimate }: { readonly estimate: NutritionEstimate }) {
  const router = useRouter();
  const target = (code: string) => estimate.targets[code];

  return (
    <DisclosureCard icon="target" style={styles.card} title="جزئیات علمی و حدود ایمنی">
      <View style={styles.links}>
        <ScienceLink label="آزمایش‌ها" onPress={() => router.push("/member/nutrition-labs")} />
        <ScienceLink label="مکمل‌ها" onPress={() => router.push("/member/nutrition-supplements")} />
      </View>

      <View accessibilityLabel="هدف‌های تغذیه تکمیلی" style={styles.targetGrid}>
        <TargetCard
          note={`حداقل مطلق ${formatValue(target("fibre")?.minimum, target("fibre")?.unit)}`}
          title="فیبر"
          value={formatValue(target("fibre")?.preferred, target("fibre")?.unit)}
        />
        <TargetCard
          note={`حد ترجیحی ${formatValue(target("free_sugar")?.preferred_maximum, target("free_sugar")?.unit)}`}
          title="قند آزاد"
          value={formatValue(target("free_sugar")?.maximum, target("free_sugar")?.unit)}
        />
        <TargetCard note="حداکثر روزانه" title="چربی اشباع" value={formatValue(target("saturated_fat")?.maximum, target("saturated_fat")?.unit)} />
        <TargetCard note="حداکثر روزانه" title="چربی ترانس" value={formatValue(target("trans_fat")?.maximum, target("trans_fat")?.unit)} />
        <TargetCard note="حداکثر روزانه" title="سدیم" value={formatValue(target("sodium")?.maximum, target("sodium")?.unit)} />
      </View>

      {estimate.micronutrients && Object.keys(estimate.micronutrients).length > 0 ? (
        <View style={styles.notes}>
          <Text style={styles.notesTitle}>مرجع ریزمغذی‌ها</Text>
          <Text style={styles.bodyText}>
            کمتر بودن دریافت غذایی از مقدار مرجع، تشخیص کمبود بالینی نیست؛ این بخش فقط برای سنجش کفایت رژیم و ترمیم برنامه است.
          </Text>
          <View style={styles.micronutrientGrid}>
            {Object.entries(estimate.micronutrients).map(([code, item]) => (
              <View key={code} style={styles.micronutrientCard}>
                <Text style={styles.micronutrientTitle}>{micronutrientLabels[code] ?? code.replaceAll("_", " ")}</Text>
                <Text style={styles.micronutrientValue}>{formatMicronutrientValue(item.target_value, item.unit)}</Text>
                <Text style={styles.micronutrientNote}>{item.reference_kind} · اطمینان: {item.confidence}</Text>
              </View>
            ))}
          </View>
        </View>
      ) : null}

      <View style={styles.notes}>
        <Text style={styles.notesTitle}>این اعداد چه معنایی دارند؟</Text>
        <Text style={styles.bodyText}>این یک برآورد علمی است، نه تشخیص یا نسخه پزشکی. نتیجه واقعی با پایش وزن، انرژی و عملکرد اصلاح می‌شود.</Text>
        <Text style={styles.bodyText}>هدف انرژی با توجه به هدف بدنی انتخاب‌شده و سهم فعالیت روزانه و تمرین ساختاریافته تنظیم می‌شود؛ پروتئین و درشت‌مغذی‌ها سپس در همان محدوده علمی هماهنگ می‌شوند.</Text>
        <Text style={styles.bodyText}>قند افزوده جداگانه ردیابی می‌شود؛ برای محدودیت سلامتی، سقف قند آزاد معیار کنترل است.</Text>
        <View style={styles.metadata}>
          <MetadataRow label="نسخه سیاست" value={estimate.policy_version} />
          <MetadataRow label="نسخه فرمول" value={estimate.formula_version} />
          <MetadataRow label="بازبینی" value={formatInteger(estimate.revision)} />
        </View>
      </View>
    </DisclosureCard>
  );
}

function ScienceLink({ label, onPress }: { readonly label: string; readonly onPress: () => void }) {
  return (
    <Pressable accessibilityLabel={label} accessibilityRole="button" onPress={onPress} style={styles.linkWrap}>
      <Text style={styles.linkText}>{label}</Text>
      <AppIcon color={fiticianTokens.colors.aqua} name="arrowLeft" size={fiticianTokens.iconSize.sm} />
    </Pressable>
  );
}

function TargetCard({ note, title, value }: { readonly note: string; readonly title: string; readonly value: string }) {
  return (
    <View style={styles.targetCard}>
      <Text style={styles.targetTitle}>{title}</Text>
      <Text style={styles.targetValue}>{value}</Text>
      <Text style={styles.targetNote}>{note}</Text>
    </View>
  );
}

function MetadataRow({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <View style={styles.metadataRow}>
      <Text style={styles.metadataLabel}>{label}</Text>
      <Text style={styles.metadataValue}>{value}</Text>
    </View>
  );
}

function formatValue(value: number | null | undefined, unit: string | undefined): string {
  if (value === null || value === undefined) return "تعیین نشده";
  const localizedUnit = unit === "kcal/day"
    ? "کیلوکالری"
    : unit === "g/day"
      ? "گرم"
      : unit === "mg/day"
        ? "میلی‌گرم"
        : unit ?? "";
  return `${formatNumber(value)} ${localizedUnit}`.trim();
}

function formatMicronutrientValue(value: number, unit: string): string {
  return `${formatNumber(value)} ${unit}`.trim();
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 1 }).format(value);
}

function formatInteger(value: number): string {
  return new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 0 }).format(value);
}

const styles = StyleSheet.create({
  bodyText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 24,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  card: {
    backgroundColor: "rgba(9, 54, 51, 0.52)",
    borderColor: "rgba(80, 223, 206, 0.18)",
    marginBottom: fiticianTokens.spacing[1],
  },
  linkText: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    paddingHorizontal: fiticianTokens.spacing[2],
    paddingVertical: fiticianTokens.spacing[2],
    textAlign: "auto",
    writingDirection: "rtl",
  },
  linkWrap: {
    alignItems: "center",
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.small,
    borderWidth: 1,
    flexDirection: "row",
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: fiticianTokens.spacing[2],
  },
  links: {
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
  },
  metadata: {
    borderTopColor: fiticianTokens.colors.line,
    borderTopWidth: 1,
    gap: fiticianTokens.spacing[2],
    paddingTop: fiticianTokens.spacing[3],
  },
  metadataLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  metadataRow: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
  },
  metadataValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "left",
    writingDirection: "ltr",
  },
  micronutrientCard: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    flex: 1,
    gap: fiticianTokens.spacing[1],
    minWidth: 120,
    padding: fiticianTokens.spacing[3],
  },
  micronutrientGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
  micronutrientNote: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 10,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  micronutrientTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  micronutrientValue: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "ltr",
  },
  notes: {
    gap: fiticianTokens.spacing[2],
  },
  notesTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  targetCard: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    flex: 1,
    gap: fiticianTokens.spacing[1],
    minWidth: 120,
    padding: fiticianTokens.spacing[3],
  },
  targetGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
  targetNote: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 10,
    lineHeight: 16,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  targetTitle: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  targetValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "ltr",
  },
});
