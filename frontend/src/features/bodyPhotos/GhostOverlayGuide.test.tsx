import { render, screen } from "@testing-library/react";
import { beforeEach, expect, it } from "vitest";

import i18n from "../../i18n";
import { GhostOverlayGuide } from "./GhostOverlayGuide";

beforeEach(async () => {
  await i18n.changeLanguage("en");
});

it.each(["front", "side", "back"] as const)("renders the privacy cut and the loose %s silhouette", (view) => {
  const { container } = render(<GhostOverlayGuide view={view} />);

  expect(screen.getByLabelText(/privacy cut/i)).toBeInTheDocument();
  expect(screen.getByText(/keep your neck and shoulders below this line/i)).toBeInTheDocument();
  expect(container.querySelector(`.ghost-overlay__silhouette--${view}`)).not.toBeNull();
});
