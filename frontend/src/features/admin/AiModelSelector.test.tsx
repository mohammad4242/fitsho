import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";

import i18n from "../../i18n";
import { AiModelSelector } from "./AiModelSelector";

it("opens a searchable model list from the model-selection control", async () => {
  await i18n.changeLanguage("en");
  const user = userEvent.setup();
  render(
    <AiModelSelector
      id="primary-model"
      label="Primary model"
      models={[
        { provider: "openrouter", model_id: "openai/gpt", display_name: "GPT", provider_family: "openai", supports_text_input: true, supports_image_input: false, supports_structured_output: true, context_length: 128000, input_price_per_token: null, output_price_per_token: null, available: true },
        { provider: "openrouter", model_id: "anthropic/claude", display_name: "Claude", provider_family: "anthropic", supports_text_input: true, supports_image_input: false, supports_structured_output: true, context_length: 200000, input_price_per_token: null, output_price_per_token: null, available: true },
      ]}
      value=""
      onChange={() => undefined}
    />,
  );

  expect(screen.queryByRole("searchbox")).not.toBeInTheDocument();
  expect(screen.queryByRole("option", { name: /GPT/ })).not.toBeInTheDocument();
  await user.click(screen.getByRole("combobox", { name: /Primary model/i }));
  expect(screen.getByRole("listbox", { name: /Primary model/i })).toBeInTheDocument();
  await user.type(screen.getByRole("searchbox"), "claude");
  expect(screen.getByRole("option", { name: /Claude/ })).toBeInTheDocument();
  expect(screen.queryByRole("option", { name: /GPT/ })).not.toBeInTheDocument();
});
