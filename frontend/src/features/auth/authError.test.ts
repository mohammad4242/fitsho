import { expect, it } from "vitest";

import i18n from "../../i18n";
import { ApiError } from "../../shared/apiClient";
import { authErrorMessage } from "./authError";

it("maps an unauthorized API error to a localized message", () => {
  expect(
    authErrorMessage(new ApiError(401, "Invalid email or password"), i18n.t),
  ).toBe("ایمیل یا رمز عبور درست نیست.");
});
