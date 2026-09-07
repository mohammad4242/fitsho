import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { useLocalSearchParams, useRouter } from "expo-router";
import { View } from "react-native";

import { Button, Notice, TextField } from "../../../ui/components";
import { AuthScaffold } from "../../../auth/AuthScaffold";
import { authCopy } from "../../../auth/copy";
import { authErrorMessage } from "../../../auth/authError";
import { authStyles } from "../../../auth/authStyles";
import { useMobileAuth } from "../../../auth/MobileAuthProvider";
import { validateConfirmation, validatePassword } from "../../../auth/validation";

interface ResetPasswordFormValues {
  confirmation: string;
  password: string;
}

function firstParam(value: string | string[] | undefined): string {
  return Array.isArray(value) ? value[0] ?? "" : value ?? "";
}

export default function ResetPasswordScreen() {
  const router = useRouter();
  const auth = useMobileAuth();
  const params = useLocalSearchParams<{ token?: string }>();
  const token = firstParam(params.token);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const { control, handleSubmit, watch } = useForm<ResetPasswordFormValues>({
    defaultValues: { confirmation: "", password: "" },
  });
  const password = watch("password");

  const submit = handleSubmit(async ({ password: newPassword }) => {
    setError(null);
    try {
      await auth.resetPassword(token, newPassword);
      setSuccess(true);
    } catch (submissionError) {
      setError(authErrorMessage(submissionError));
    }
  });

  return (
    <AuthScaffold
      subtitle={authCopy.passwordRecovery.resetSubtitle}
      title={authCopy.passwordRecovery.resetTitle}
    >
      <View style={authStyles.content}>
        {!token ? <Notice message={authCopy.passwordRecovery.invalidToken} variant="danger" /> : null}
        {error ? <Notice message={error} variant="danger" /> : null}
        {success ? <Notice message={authCopy.passwordRecovery.resetSuccess} variant="success" /> : null}
        <Controller
          control={control}
          name="password"
          rules={{ required: "رمز عبور را وارد کنید.", validate: validatePassword }}
          render={({ field, fieldState }) => (
            <TextField
              autoCapitalize="none"
              autoComplete="new-password"
              editable={Boolean(token) && !success}
              error={fieldState.error?.message}
              label={authCopy.passwordRecovery.newPassword}
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
              editable={Boolean(token) && !success}
              error={fieldState.error?.message}
              label={authCopy.passwordRecovery.confirmPassword}
              onBlur={field.onBlur}
              onChangeText={field.onChange}
              secureTextEntry
              textContentType="newPassword"
              value={field.value}
            />
          )}
        />
        {!success ? (
          <Button
            disabled={!token}
            label={authCopy.passwordRecovery.resetSubmit}
            loading={auth.busy}
            onPress={submit}
          />
        ) : null}
        <Button
          label={authCopy.passwordRecovery.backToLogin}
          onPress={() => router.replace("/auth/sign-in")}
          variant="ghost"
        />
      </View>
    </AuthScaffold>
  );
}
