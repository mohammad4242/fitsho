import { useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Image,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import * as ImagePicker from "expo-image-picker";
import { File } from "expo-file-system";
import type { MultipartUploadRequest } from "@fitician/core";

import { getMobileRuntimeConfig } from "../config/nativeRuntimeConfig";
import { useMobileAuth } from "../auth/MobileAuthProvider";
import { useAndroidBackHandler } from "../ui/navigation/BackBehaviorProvider";
import { Button, Card, Notice } from "../ui/components";
import { fiticianTokens } from "../ui/tokens";
import {
  PROFILE_PHOTO_PICKER_OPTIONS,
  createProfilePhotoUploadJob,
  profilePhotoErrorMessage,
  profilePhotoMimeTypeForAsset,
  resolveProfilePhotoUrl,
  type ProfilePhotoResponse,
} from "./profilePhoto";
import {
  UploadCancellationError,
  UploadManager,
  type UploadHandle,
} from "../upload/uploadManager";

export interface ProfilePhotoControlProps {
  readonly initialUrl?: string | null;
  readonly label: string;
  readonly onChanged?: (url: string | null) => void;
}

type PhotoAction = "pick" | "delete" | null;

export function ProfilePhotoControl({
  initialUrl,
  label,
  onChanged,
}: ProfilePhotoControlProps) {
  const auth = useMobileAuth();
  const runtime = getMobileRuntimeConfig();
  const [url, setUrl] = useState<string | null>(initialUrl ?? null);
  const [action, setAction] = useState<PhotoAction>(null);
  const [error, setError] = useState<string | null>(null);
  const uploadRef = useRef<UploadHandle<ProfilePhotoResponse> | null>(null);
  const manager = useMemo(
    () => new UploadManager({
      executor: async <TResponse,>(request: MultipartUploadRequest) => auth.upload<TResponse>(request),
    }),
    [auth.upload],
  );

  useEffect(() => {
    setUrl(initialUrl ?? null);
  }, [initialUrl]);

  useAndroidBackHandler(
    "upload",
    () => {
      const upload = uploadRef.current;
      if (upload === null || action !== "pick") return false;
      upload.cancel();
      return true;
    },
    action === "pick",
  );

  async function pickPhoto() {
    if (action !== null) return;
    setError(null);
    setAction("pick");
    try {
      const result = await ImagePicker.launchImageLibraryAsync(PROFILE_PHOTO_PICKER_OPTIONS);
      if (result.canceled) return;
      const asset = result.assets[0];
      if (asset === undefined) throw new Error("No profile photo was selected");
      const mimeType = profilePhotoMimeTypeForAsset(asset.mimeType, asset.uri);
      if (mimeType === null) throw new Error("Unsupported profile photo format");
      const bytes = new Uint8Array(await new File(asset.uri).arrayBuffer());
      const handle = manager.enqueue<ProfilePhotoResponse>(createProfilePhotoUploadJob({
        bytes,
        height: asset.height,
        mimeType,
        width: asset.width,
      }));
      uploadRef.current = handle;
      const response = await handle.promise;
      const nextUrl = resolveProfilePhotoUrl(response.profile_photo_url, runtime.apiBaseUrl);
      setUrl(nextUrl);
      onChanged?.(nextUrl);
    } catch (cause) {
      if (!(cause instanceof UploadCancellationError)) {
        setError(profilePhotoErrorMessage(cause));
      }
    } finally {
      uploadRef.current = null;
      setAction(null);
    }
  }

  async function deletePhoto() {
    if (action !== null || url === null) return;
    setError(null);
    setAction("delete");
    try {
      await auth.request<void>({ method: "DELETE", path: "/api/v1/profile/photo" });
      setUrl(null);
      onChanged?.(null);
    } catch (cause) {
      setError(profilePhotoErrorMessage(cause));
    } finally {
      setAction(null);
    }
  }

  return (
    <Card style={styles.card}>
      <View style={styles.identityRow}>
        {url === null ? (
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>{label.trim().slice(0, 1) || "ف"}</Text>
          </View>
        ) : (
          <Image accessibilityLabel={label} source={{ uri: url }} style={styles.photo} />
        )}
        <View style={styles.copy}>
          <Text style={styles.title}>تصویر پروفایل</Text>
          <Text style={styles.description}>اختیاری؛ عکس مربعی فقط برای حساب خودت ذخیره می‌شود.</Text>
        </View>
      </View>
      {error !== null ? <Notice message={error} variant="danger" /> : null}
      <View style={styles.actions}>
        <Button
          disabled={action !== null}
          label={url === null ? "افزودن عکس" : "تعویض عکس"}
          loading={action === "pick"}
          onPress={() => void pickPhoto()}
        />
        {url !== null ? (
          <Pressable
            accessibilityRole="button"
            accessibilityState={{ disabled: action !== null }}
            disabled={action !== null}
            onPress={() => void deletePhoto()}
            style={styles.deleteButton}
          >
            {action === "delete" ? (
              <ActivityIndicator color={fiticianTokens.colors.coral} />
            ) : (
              <Text style={styles.deleteText}>حذف عکس</Text>
            )}
          </Pressable>
        ) : null}
      </View>
    </Card>
  );
}

const styles = StyleSheet.create({
  actions: {
    alignItems: "center",
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
  },
  avatar: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.aqua,
    borderRadius: fiticianTokens.radii.pill,
    height: 64,
    justifyContent: "center",
    width: 64,
  },
  avatarText: {
    color: fiticianTokens.colors.canvas,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h2,
  },
  card: {
    gap: fiticianTokens.spacing[3],
  },
  copy: {
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  deleteButton: {
    alignItems: "center",
    borderColor: fiticianTokens.colors.coral,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    justifyContent: "center",
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    minWidth: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: fiticianTokens.spacing[3],
  },
  deleteText: {
    color: fiticianTokens.colors.coral,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    writingDirection: "rtl",
  },
  description: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 19,
    textAlign: "right",
    writingDirection: "rtl",
  },
  identityRow: {
    alignItems: "center",
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
  },
  photo: {
    backgroundColor: fiticianTokens.colors.surfaceRaised,
    borderRadius: fiticianTokens.radii.pill,
    height: 64,
    width: 64,
  },
  title: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.lg,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
});
