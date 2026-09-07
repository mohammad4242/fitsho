export type User = {
  id: string;
  email: string | null;
  phone_number: string | null;
  created_at: string;
  is_admin: boolean;
  profile_photo_url?: string | null;
};

export type GenericMessage = {
  message: string;
};

export type PhoneOtpSent = GenericMessage & {
  retry_after_seconds: number;
};

export type Credentials = {
  email: string;
  password: string;
};
