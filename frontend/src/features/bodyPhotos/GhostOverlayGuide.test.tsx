import { render, screen } from "@testing-library/react";
import { beforeEach, expect, it } from "vitest";

import i18n from "../../i18n";
import { GhostOverlayGuide } from "./GhostOverlayGuide";
import { resolveGhostOverlayVariant } from "./ghostOverlayAssets";
import { ghostGuideTransformStyle } from "./ghostPhotoEditor";

beforeEach(async () => {
  await i18n.changeLanguage("en");
});

it.each([
  ["male", "front", "photo_2026-09-02_13-27-40.jpg"],
  ["male", "side", "photo_2026-09-02_13-27-41 (2).jpg"],
  ["male", "back", "photo_2026-09-02_13-27-39.jpg"],
  ["female", "front", "photo_2026-09-02_13-54-09.jpg"],
  ["female", "side", "photo_2026-09-02_13-27-41.jpg"],
  ["female", "back", "photo_2026-09-02_13-27-42.jpg"],
] as const)("renders the prepared %s %s ghost asset", (sex, view, fileName) => {
  const { container } = render(<GhostOverlayGuide sex={sex} view={view} />);
  const image = container.querySelector(".ghost-overlay__asset");

  expect(screen.getByLabelText(/privacy cut/i)).toBeInTheDocument();
  expect(screen.getByText(/keep your neck and shoulders below this line/i)).toBeInTheDocument();
  expect(image).toHaveAttribute("src", expect.stringContaining(fileName.replace(" ", "%20")));
  expect(image).toHaveAttribute("alt", "");
  expect(container.querySelector("svg")).toBeNull();
});

it.each([undefined, null, "other", "prefer_not_to_say"] as const)(
  "uses the prepared neutral fallback for %s sex",
  (sex) => {
    const { container } = render(<GhostOverlayGuide sex={sex} view="side" />);

    expect(resolveGhostOverlayVariant(sex)).toBe("neutral");
    expect(container.querySelector(".ghost-overlay__asset")).toHaveAttribute(
      "src",
      expect.stringContaining("photo_2026-09-02_13-27-41%20(2).jpg"),
    );
  },
);

it("applies only a uniform centered scale to the fixed Ghost asset frame", () => {
  const { container } = render(<GhostOverlayGuide sex="female" view="front" ghostScale={0.95} />);
  const frame = container.querySelector<HTMLElement>(".ghost-overlay__asset-frame");

  expect(frame).not.toBeNull();
  expect(frame).toHaveStyle({ transform: ghostGuideTransformStyle(0.95) });
});

it("uses the selected female Ghost visible top for each view", () => {
  const back = render(<GhostOverlayGuide sex="female" view="back" />);
  expect(back.getByLabelText(/privacy cut/i)).toHaveStyle({ top: "2.281%" });
  back.unmount();

  const front = render(<GhostOverlayGuide sex="female" view="front" />);
  expect(front.getByLabelText(/privacy cut/i)).toHaveStyle({ top: "10.981%" });
});

it("renders the privacy line from the transformed Ghost neck anchor", () => {
  const { container } = render(
    <GhostOverlayGuide
      sex="female"
      view="front"
      ghostScale={1}
    />,
  );

  expect(container.querySelector(".ghost-overlay__privacy-cut")).toHaveStyle({ top: "10.981%" });
});

it("keeps the visible privacy line centered when the photo moves", () => {
  const { container } = render(
    <GhostOverlayGuide
      sex="female"
      view="front"
      ghostScale={1}
    />,
  );

  expect(container.querySelector(".ghost-overlay__privacy-cut")).toHaveStyle({
    left: "0%",
    width: "100%",
  });
});

it("keeps the privacy line attached when the Ghost is scaled", () => {
  const { container } = render(
    <GhostOverlayGuide
      sex="female"
      view="front"
      ghostScale={0.8}
    />,
  );

  expect(container.querySelector(".ghost-overlay__privacy-cut")).toHaveStyle({
    top: "18.785%",
    left: "10%",
    width: "80%",
  });
});

it("places the side privacy cut line on the Ghost top and scales dynamically", () => {
  const defaultScale = render(<GhostOverlayGuide sex="female" view="side" ghostScale={1} />);
  expect(defaultScale.container.querySelector(".ghost-overlay__privacy-cut")).toHaveStyle({
    top: "10.993%",
  });
  defaultScale.unmount();

  const scaledDown = render(<GhostOverlayGuide sex="female" view="side" ghostScale={0.8} />);
  expect(scaledDown.container.querySelector(".ghost-overlay__privacy-cut")).toHaveStyle({
    top: "18.794%",
    left: "10%",
    width: "80%",
  });
  scaledDown.unmount();

  const scaledUp = render(<GhostOverlayGuide sex="female" view="side" ghostScale={1.15} />);
  expect(scaledUp.container.querySelector(".ghost-overlay__privacy-cut")).toHaveStyle({
    top: "5.142%",
    left: "-7.5%",
    width: "115%",
  });
});

it.each(["male", "female"] as const)(
  "aligns side and back privacy cuts for the %s Ghost",
  (sex) => {
    const side = render(<GhostOverlayGuide sex={sex} view="side" />);
    expect(side.getByLabelText(/privacy cut/i)).toHaveStyle({
      top: sex === "female" ? "10.993%" : "10.425%",
    });
    side.unmount();

    const back = render(<GhostOverlayGuide sex={sex} view="back" />);
    expect(back.getByLabelText(/privacy cut/i)).toHaveStyle({
      top: sex === "female" ? "2.281%" : "1.594%",
    });
  },
);

it("mirrors only the side Ghost for a left profile", () => {
  const { container } = render(
    <GhostOverlayGuide
      sex="female"
      view="side"
      sideProfile="left"
      ghostScale={0.95}
    />,
  );
  const frame = container.querySelector<HTMLElement>(".ghost-overlay__asset-frame");

  expect(frame).toHaveStyle({
    transform: ghostGuideTransformStyle(0.95, true),
  });
});

it("marks the asset frame with the sex variant for view alignment", () => {
  const { container } = render(
    <GhostOverlayGuide
      sex="female"
      view="front"
    />,
  );
  const frame = container.querySelector(".ghost-overlay__asset-frame");
  const asset = container.querySelector(".ghost-overlay__asset");
  expect(frame).toHaveClass("ghost-overlay__asset-frame--female");
  expect(frame).toHaveClass("ghost-overlay__asset-frame--front");
  expect(asset).toHaveStyle({
    position: "relative",
    top: "-2.7%",
    transform: "scale(0.78)",
  });
});
