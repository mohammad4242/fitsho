export type User = {
  id: string;
  email: string;
  created_at: string;
};

export type Credentials = {
  email: string;
  password: string;
};

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}
