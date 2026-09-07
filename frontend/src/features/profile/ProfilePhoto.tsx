import { useEffect, useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "../../shared/apiClient";
import * as api from "./api";
import "./profilePhoto.css";

const MAX_FILE_BYTES = 5 * 1024 * 1024;
const SUPPORTED_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

export type ProfilePhotoAvatarProps = {
  url?: string | null;
  label: string;
  size?: "sm" | "md" | "lg";
  className?: string;
};

export function ProfilePhotoAvatar({
  url,
  label,
  size = "md",
  className,
}: ProfilePhotoAvatarProps) {
  const initial = label.trim().charAt(0).toLocaleUpperCase() || "ف";
  const classes = ["profile-photo-avatar", `profile-photo-avatar--${size}`, className]
    .filter(Boolean)
    .join(" ");

  if (url) {
    return <img className={classes} src={url} alt={label} />;
  }
  return <span className={classes} role="img" aria-label={label}>{initial}</span>;
}

export type ProfilePhotoControlProps = {
  initialUrl?: string | null;
  label: string;
  onChanged?: (url: string | null) => void;
  className?: string;
};

export function ProfilePhotoControl({
  initialUrl,
  label,
  onChanged,
  className,
}: ProfilePhotoControlProps) {
  const { i18n } = useTranslation();
  const fa = i18n.resolvedLanguage !== "en";
  const l = (persian: string, english: string) => fa ? persian : english;
  const inputId = useId();
  const [url, setUrl] = useState(initialUrl ?? null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState<"upload" | "delete" | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setUrl(initialUrl ?? null);
  }, [initialUrl]);

  useEffect(() => {
    return () => {
      if (previewUrl !== null && typeof URL.revokeObjectURL === "function") {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  function chooseFile(file: File | undefined) {
    if (file === undefined) return;
    if (!SUPPORTED_TYPES.has(file.type)) {
      setError(l("فرمت عکس پشتیبانی نمی‌شود", "This image format is not supported"));
      return;
    }
    if (file.size > MAX_FILE_BYTES) {
      setError(l("حجم عکس باید کمتر از ۵ مگابایت باشد", "The image must be smaller than 5 MB"));
      return;
    }
    setError(null);
    setSelectedFile(file);
    setPreviewUrl(typeof URL.createObjectURL === "function" ? URL.createObjectURL(file) : null);
  }

  function clearSelection() {
    setSelectedFile(null);
    setPreviewUrl(null);
  }

  async function upload() {
    if (selectedFile === null || busy !== null) return;
    setBusy("upload");
    setError(null);
    try {
      const cropped = await cropToSquare(selectedFile);
      const uploaded = await api.uploadProfilePhoto(cropped);
      setUrl(uploaded.profile_photo_url);
      onChanged?.(uploaded.profile_photo_url);
      clearSelection();
    } catch (cause) {
      setError(photoError(cause, l));
    } finally {
      setBusy(null);
    }
  }

  async function remove() {
    if (busy !== null || !url || !window.confirm(l("عکس پروفایل حذف شود؟", "Remove this profile photo?"))) return;
    setBusy("delete");
    setError(null);
    try {
      await api.deleteProfilePhoto();
      setUrl(null);
      onChanged?.(null);
    } catch (cause) {
      setError(photoError(cause, l));
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className={["profile-photo-control", className].filter(Boolean).join(" ")} aria-label={l("عکس پروفایل", "Profile photo")}>
      <div className="profile-photo-control__identity">
        <ProfilePhotoAvatar url={url} label={label} size="lg" />
        <div>
          <strong>{l("تصویر حساب", "Account image")}</strong>
          <p>{l("یک تصویر مربعی انتخاب کن تا در حساب و فضای متخصص نمایش داده شود.", "Choose a square image to use across your account and specialist workspace.")}</p>
        </div>
      </div>
      <div className="profile-photo-control__actions">
        <label className="profile-photo-control__upload" htmlFor={inputId}>
          {url ? l("تعویض عکس", "Change photo") : l("افزودن عکس", "Add photo")}
        </label>
        <input
          id={inputId}
          className="profile-photo-control__input"
          type="file"
          accept="image/jpeg,image/png,image/webp"
          aria-label={l("انتخاب عکس پروفایل", "Choose profile photo")}
          disabled={busy !== null}
          onChange={(event) => {
            chooseFile(event.currentTarget.files?.[0]);
            event.currentTarget.value = "";
          }}
        />
        {url && (
          <button className="profile-photo-control__remove" type="button" disabled={busy !== null} onClick={() => void remove()}>
            {busy === "delete" ? l("در حال حذف…", "Removing…") : l("حذف عکس", "Remove photo")}
          </button>
        )}
      </div>
      {error && <p className="profile-photo-control__error" role="alert">{error}</p>}
      {selectedFile && (
        <div className="profile-photo-dialog-backdrop">
          <section className="profile-photo-dialog" role="dialog" aria-modal="true" aria-labelledby={`${inputId}-title`}>
            <header>
              <div>
                <p>{l("پیش‌نمایش", "Preview")}</p>
                <h2 id={`${inputId}-title`}>{l("قاب مربعی عکس", "Square photo crop")}</h2>
              </div>
              <button className="profile-photo-dialog__close" type="button" onClick={clearSelection} disabled={busy !== null} aria-label={l("بستن پیش‌نمایش", "Close preview")}>×</button>
            </header>
            <div className="profile-photo-dialog__preview">
              {previewUrl ? <img src={previewUrl} alt={l("پیش‌نمایش عکس پروفایل", "Profile photo preview")} /> : <span>{selectedFile.name}</span>}
            </div>
            <p className="profile-photo-dialog__hint">{l("از مرکز تصویر به‌صورت مربعی برش می‌خورد.", "The image will be cropped to a square from the center.")}</p>
            <footer>
              <button className="profile-photo-dialog__cancel" type="button" onClick={clearSelection} disabled={busy !== null}>{l("انصراف", "Cancel")}</button>
              <button className="profile-photo-dialog__save" type="button" onClick={() => void upload()} disabled={busy !== null}>
                {busy === "upload" ? l("در حال ذخیره…", "Saving…") : l("تأیید و ذخیره", "Confirm and save")}
              </button>
            </footer>
          </section>
        </div>
      )}
    </section>
  );
}

function photoError(
  cause: unknown,
  l: (persian: string, english: string) => string,
): string {
  if (cause instanceof ApiError) {
    if (cause.code === "invalid_file_size") return l("حجم عکس مجاز نیست.", "The image size is not allowed.");
    if (cause.code === "invalid_geometry") return l("عکس باید مربعی باشد.", "The image must be square.");
    if (cause.code === "unsupported_format") return l("فرمت عکس پشتیبانی نمی‌شود.", "This image format is not supported.");
  }
  return l("ذخیره عکس انجام نشد. دوباره تلاش کن.", "The photo could not be saved. Try again.");
}

async function cropToSquare(file: File): Promise<File> {
  if (typeof URL.createObjectURL !== "function") throw new Error("Preview is unavailable");
  const sourceUrl = URL.createObjectURL(file);
  try {
    const image = await new Promise<HTMLImageElement>((resolve, reject) => {
      const element = new Image();
      element.onload = () => resolve(element);
      element.onerror = () => reject(new Error("Invalid image"));
      element.src = sourceUrl;
    });
    const width = image.naturalWidth || image.width;
    const height = image.naturalHeight || image.height;
    const size = Math.min(width, height);
    if (!size) throw new Error("Invalid image dimensions");
    const canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Canvas is unavailable");
    context.drawImage(image, (width - size) / 2, (height - size) / 2, size, size, 0, 0, size, size);
    const blob = await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob((value) => value ? resolve(value) : reject(new Error("Canvas export failed")), "image/jpeg", 0.9);
    });
    return new File([blob], "profile-photo.jpg", { type: "image/jpeg" });
  } finally {
    URL.revokeObjectURL(sourceUrl);
  }
}
