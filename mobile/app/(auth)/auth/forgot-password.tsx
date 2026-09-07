import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { useRouter } from "expo-router";
import { View } from "react-native";

import { Button, Notice, TextField } from "../../../ui/components";
import { AuthScaffold } from "../../../auth/AuthScaffold";
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
      subtitle={authCopy.passwordRecovery.forgotSubtitle}
      title={authCopy.passwordRecovery.forgotTitle}
    >
      <View style={authStyles.content}>
        {error ? <Notice message={error} variant="danger" /> : null}
        {success ? <Notice message={authCopy.passwordRecovery.forgotSuccess} variant="success" /> : null}
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
        <Button label={authCopy.passwordRecovery.forgotSubmit} loading={auth.busy} onPress={submit} />
        <Button
          label={authCopy.passwordRecovery.backToLogin}
          onPress={() => router.replace("/auth/sign-in")}
          variant="ghost"
        />
      </View>
    </AuthScaffold>
  );
}
