import { type ReactNode, useEffect } from "react";
import { Pressable, Text, View } from "react-native";

import { AppIcon } from "../../ui/components";
import { fiticianDirectionalIconName } from "../../ui/icons";
import { fiticianTokens } from "../../ui/tokens";
import { publicOnboardingStyles as styles } from "./publicOnboardingStyles";

export interface PublicQuestionFrameProps {
  readonly activeStage: number;
  readonly children: ReactNode;
  readonly description?: string;
  readonly onBack: () => void;
  readonly onRegisterBack?: (handler: () => void) => () => void;
  readonly progressLabel: string;
  readonly question: number;
  readonly stageLabel: string;
  readonly stages: readonly string[];
  readonly title: string;
  readonly totalQuestions: number;
  readonly footer?: ReactNode;
  readonly hideStageTrack?: boolean;
  readonly testID?: string;
}

export function PublicQuestionFrame({
  activeStage,
  children,
  description,
  footer,
  hideStageTrack = false,
  onBack,
  onRegisterBack,
  progressLabel,
  question,
  stageLabel,
  stages,
  testID,
  title,
  totalQuestions,
}: PublicQuestionFrameProps) {
  const percentage = `${Math.max(0, Math.min(100, ((question + 1) / totalQuestions) * 100))}%`;

  useEffect(() => onRegisterBack?.(onBack), [onBack, onRegisterBack]);

  return (
    <View accessibilityLabel={stageLabel} style={styles.question} testID={testID}>
      <Pressable
        accessibilityLabel="بازگشت"
        accessibilityRole="button"
        onPress={onBack}
        style={styles.backButton}
      >
        <AppIcon color={fiticianTokens.colors.mist} name={fiticianDirectionalIconName("back")} size={20} />
      </Pressable>
      {!hideStageTrack ? (
        <View accessibilityLabel={stageLabel} style={styles.stageRow}>
          {stages.map((stage, index) => {
            const complete = index < activeStage;
            const active = index === activeStage;
            return (
              <View key={stage} style={styles.stageItem}>
                <View
                  style={[
                    styles.stageMarker,
                    active && styles.stageMarkerActive,
                    complete && styles.stageMarkerComplete,
                  ]}
                >
                  <Text
                    style={[
                      styles.stageMarkerText,
                      active && styles.stageMarkerTextActive,
                      complete && styles.stageMarkerTextComplete,
                    ]}
                  >
                    {complete ? "✓" : index + 1}
                  </Text>
                </View>
                <Text
                  numberOfLines={1}
                  style={[
                    styles.stageLabel,
                    active && styles.stageLabelActive,
                    complete && styles.stageLabelComplete,
                  ]}
                >
                  {stage}
                </Text>
              </View>
            );
          })}
        </View>
      ) : null}
      <View
        accessibilityLabel={progressLabel}
        accessibilityRole="progressbar"
        accessibilityValue={{ max: totalQuestions, min: 1, now: question + 1 }}
        style={styles.progressStack}
      >
        <Text style={styles.progressLabel}>{progressLabel}</Text>
        <View style={styles.progressBar}>
          <View style={[styles.progressFill, { width: percentage as `${number}%` }]} />
        </View>
      </View>
      <Text accessibilityRole="header" style={styles.questionTitle}>{title}</Text>
      {description ? <Text style={styles.questionDescription}>{description}</Text> : null}
      <View style={styles.questionForm}>
        {children}
        {footer ? <View style={styles.footer}>{footer}</View> : null}
      </View>
    </View>
  );
}

export interface PublicChoiceOption {
  readonly description?: string;
  readonly icon?: React.ComponentProps<typeof AppIcon>["name"];
  readonly label: string;
  readonly layout?: "default" | "sex";
  readonly selectionRole?: "checkbox" | "radio";
  readonly value: string;
}

export function PublicChoiceCard({
  description,
  disabled = false,
  icon,
  layout = "default",
  label,
  onPress,
  selectionRole = "radio",
  selected,
}: PublicChoiceOption & {
  readonly disabled?: boolean;
  readonly onPress: () => void;
  readonly selected: boolean;
}) {
  const isSexLayout = layout === "sex";
  return (
    <Pressable
      accessibilityLabel={label}
      accessibilityRole={selectionRole}
      accessibilityState={selectionRole === "checkbox" ? { checked: selected, disabled } : { disabled, selected }}
      disabled={disabled}
      onPress={onPress}
      style={[
        styles.choiceCard,
        !icon && styles.choiceCardCentered,
        isSexLayout && styles.sexChoiceCard,
        selected && styles.choiceCardSelected,
        disabled && styles.choiceCardDisabled,
      ]}
    >
      {icon ? (
        <View style={[styles.choiceIcon, isSexLayout && styles.sexChoiceIcon, selected && styles.choiceIconSelected]}>
          <AppIcon
            color={selected ? fiticianTokens.colors.canvas : fiticianTokens.colors.aqua}
            name={icon}
            size={22}
          />
        </View>
      ) : null}
      <View style={[styles.choiceContent, !icon && styles.choiceContentCentered, isSexLayout && styles.sexChoiceContent]}>
        <Text style={[styles.choiceLabel, !icon && styles.choiceLabelCentered, isSexLayout && styles.sexChoiceLabel]}>{label}</Text>
        {description ? <Text style={styles.choiceDescription}>{description}</Text> : null}
      </View>
    </Pressable>
  );
}
