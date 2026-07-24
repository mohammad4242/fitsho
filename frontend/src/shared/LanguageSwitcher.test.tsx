import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it } from "vitest";

import i18n from "../i18n";
import { LanguageSwitcher } from "./LanguageSwitcher";

afterEach(async () => {
  localStorage.clear();
  await i18n.changeLanguage("fa");
});

it("changes the document language, direction, and stored preference", async () => {
  const user = userEvent.setup();
  render(<LanguageSwitcher />);

  await user.click(screen.getByRole("button", { name: "English" }));

  expect(document.documentElement).toHaveAttribute("lang", "en");
  expect(document.documentElement).toHaveAttribute("dir", "ltr");
  expect(localStorage.getItem("fitsho-language")).toBe("en");
  expect(screen.getByRole("button", { name: "فارسی" })).toBeInTheDocument();
});
