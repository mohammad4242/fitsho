import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { useLocalSearchParams, useRouter } from "expo-router";
import { View } from "react-native";

import { Button, Notice, TextField } from "../../../ui/components";
import { AuthFormSection, AuthScaffold } from "../../../auth/AuthScaffold";
import { publicOnboardingParams } from "../../../auth/authRoute";
import { authCopy } from "../../../auth/copy";
import { authErrorMessage } from "../../../auth/authError";
import { authStyles } from "../../../auth/authStyles";
import { useMobileAuth } from "../../../auth/MobileAuthProvider";
import { validateEmail } from "../../../auth/validation";

interface ForgotPasswordFormValues {
  email: string;
}

export default function ForgotPasswordScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ source?: string }>();
  const auth = useMobileAuth();
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const { control, handleSubmit } = useForm<ForgotPasswordFormValues>({ defaultValues: { email: "" } });

  const submit = handleSubmit(async ({ email }) => {
    setError(null);
    try {
      await auth.forgotPassword(email.trim());
      setSuccess(true);
    } catch (submissionError) {
      setError(authErrorMessage(submissionError));
    }
  });

  return (
    <AuthScaffold
      eyebrow={authCopy.passwordRecovery.eyebrow}
      subtitle={authCopy.passwordRecovery.forgotSubtitle}
      title={authCopy.passwordRecovery.forgotTitle}
    >
      <View style={authStyles.content}>
        {success ? <Notice message={authCopy.passwordRecovery.forgotSuccess} variant="success" /> : null}
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
                textContentType="emailAddress"
                textDirection="ltr"
                value={field.value}
              />
            )}
          />
          {error ? <Notice message={error} variant="danger" /> : null}
          <Button label={authCopy.passwordRecovery.forgotSubmit} loading={auth.busy} onPress={submit} />
          <Button
            label={authCopy.passwordRecovery.backToLogin}
            onPress={() => router.replace({ pathname: "/auth/sign-in", params: publicOnboardingParams(params.source) })}
            variant="ghost"
          />
        </AuthFormSection>
      </View>
    </AuthScaffold>
  );
}
