import { fireEvent, render, screen } from "@testing-library/react-native";
import { expect, jest, test } from "@jest/globals";
import { NutritionThumbnail } from "./NutritionThumbnail";

jest.mock("../config/nativeRuntimeConfig", () => ({ getMobileRuntimeConfig: () => ({ apiBaseUrl: "https://api.example.test" }) }));
jest.mock("../ui/components/AppIcon", () => ({ AppIcon: () => null }));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => null }));

test("resolves relative media, shows loading, and falls back on image error", () => {
  render(<NutritionThumbnail imageUrl="/media/meal.webp" name="عدسی" />);
  const image = screen.getByLabelText("تصویر عدسی");
  expect(image.props.source.uri).toBe("https://api.example.test/media/meal.webp");
  expect(screen.getByLabelText("در حال بارگذاری تصویر")).toBeTruthy();
  fireEvent(image, "error");
  expect(screen.queryByLabelText("در حال بارگذاری تصویر")).toBeNull();
  expect(screen.getByLabelText("تصویر عدسی موجود نیست")).toBeTruthy();
});

test("preserves absolute URLs and recovers when the image changes", () => {
  const view = render(<NutritionThumbnail imageUrl={null} name="عدسی" />);
  expect(screen.getByLabelText("تصویر عدسی موجود نیست")).toBeTruthy();
  view.rerender(<NutritionThumbnail imageUrl="https://cdn.example.test/a.webp" name="عدسی" />);
  const image = screen.getByLabelText("تصویر عدسی");
  expect(image.props.source.uri).toBe("https://cdn.example.test/a.webp");
  fireEvent(image, "load");
  expect(screen.queryByLabelText("در حال بارگذاری تصویر")).toBeNull();
});
