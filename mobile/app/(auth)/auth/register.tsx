import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { Pressable, Text, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";

import { Button, Notice, TextField } from "../../../ui/components";
import { AuthFormSection, AuthScaffold } from "../../../auth/AuthScaffold";
import { onboardingRoute, publicOnboardingParams } from "../../../auth/authRoute";
import { authCopy, mobileAuthCopy } from "../../../auth/copy";
import { authErrorMessage } from "../../../auth/authError";
import { authStyles } from "../../../auth/authStyles";
import { useMobileAuth } from "../../../auth/MobileAuthProvider";
import { validateConfirmation, validateEmail, validatePassword } from "../../../auth/validation";

interface RegisterFormValues {
  email: string;
  password: string;
  confirmation: string;
}

export default function RegisterScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ source?: string }>();
  const auth = useMobileAuth();
  const [error, setError] = useState<string | null>(null);
  const [complete, setComplete] = useState(false);
  const { control, handleSubmit, watch } = useForm<RegisterFormValues>({
    defaultValues: { confirmation: "", email: "", password: "" },
  });
  const password = watch("password");

  const submit = handleSubmit(async (values) => {
    setError(null);
    try {
      await auth.register({ email: values.email.trim(), password: values.password });
      setComplete(true);
      router.replace(onboardingRoute(params.source));
    } catch (submissionError) {
      setError(authErrorMessage(submissionError));
    }
  });

  return (
    <AuthScaffold
      eyebrow={authCopy.register.eyebrow}
      subtitle={authCopy.register.subtitle}
      title={authCopy.register.title}
    >
      <View style={authStyles.content}>
        {complete ? <Notice message={mobileAuthCopy.registrationComplete} variant="success" /> : null}
        <AuthFormSection>
          <Controller
            control={control}
            name="email"
            rules={{ required: "ایمیل را وارد کنید.", validate: validateEmail }}
            render={({ field, fieldState }) => (
              <TextField
                autoCapitalize="none"
                autoComplete="email"
                error={fieldState.error?.message}
                keyboardType="email-address"
                label={authCopy.common.email}
                onBlur={field.onBlur}
                onChangeText={field.onChange}
                placeholder="name@example.com"
                textContentType="emailAddress"
                textDirection="ltr"
                value={field.value}
              />
            )}
          />
          <View style={authStyles.fieldHeading}>
            <Text style={authStyles.fieldLabel}>{authCopy.common.password}</Text>
            <Text style={authStyles.inlineLink}>{authCopy.register.passwordHint}</Text>
          </View>
          <Controller
            control={control}
            name="password"
            rules={{ required: "رمز عبور را وارد کنید.", validate: validatePassword }}
            render={({ field, fieldState }) => (
              <TextField
                autoCapitalize="none"
                autoComplete="new-password"
                error={fieldState.error?.message}
                accessibilityLabel={authCopy.common.password}
                maxLength={128}
                onBlur={field.onBlur}
                onChangeText={field.onChange}
                secureTextEntry
                textContentType="newPassword"
                value={field.value}
              />
            )}
          />
          <Controller
            control={control}
            name="confirmation"
            rules={{
              required: "تکرار رمز عبور را وارد کنید.",
              validate: (value) => validateConfirmation(value, password),
            }}
            render={({ field, fieldState }) => (
              <TextField
                autoCapitalize="none"
                autoComplete="new-password"
                error={fieldState.error?.message}
                label={authCopy.register.confirmPassword}
                maxLength={128}
                onBlur={field.onBlur}
                onChangeText={field.onChange}
                secureTextEntry
                textContentType="newPassword"
                value={field.value}
              />
            )}
          />
          {error ? <Notice message={error} variant="danger" /> : null}
          <Button label={authCopy.register.submit} loading={auth.busy} onPress={submit} />
        </AuthFormSection>
        <View style={authStyles.footer}>
          <Text style={authStyles.footerText}>{authCopy.register.hasAccount}</Text>
          <Pressable accessibilityRole="button" onPress={() => router.replace({ pathname: "/auth/sign-in", params: publicOnboardingParams(params.source) })}>
            <Text style={authStyles.link}>{authCopy.register.loginLink}</Text>
          </Pressable>
        </View>
      </View>
    </AuthScaffold>
  );
}
