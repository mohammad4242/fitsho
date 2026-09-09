import { readFile } from "node:fs/promises";
import { expect, it } from "vitest";

it("keeps native deletion access authenticated, exact-confirmed, and linked to external policy pages", async () => {
  const route = await readFile(
    new URL("../app/(account)/account-deletion.tsx", import.meta.url),
    "utf8",
  );
  const source = await readFile(new URL("./AccountDeletionScreen.tsx", import.meta.url), "utf8");
  expect(route).toContain("AccountDeletionScreen");
  expect(source).toContain('confirmation === "DELETE"');
  expect(source).toContain("/privacy");
  expect(source).toContain("/delete-account");
  expect(source).toContain("accountDeletionError");
  expect(source).toContain("auth.logout");
  expect(source).toContain("حذف حساب فیتشو");
  expect(source).toContain("درخواست حذف حساب را از همین صفحه ثبت کن");
  expect(source).toContain("تا پیش از این زمان می‌توانی درخواست را لغو کنی");
  expect(source).toContain("صفحه حذف حساب در وب");
  expect(source).toContain("PageHeading");
});
