export type NativeFontDefinition = {
  readonly path: string;
  readonly weight: number;
  readonly style?: "normal";
};

export type NativeFontFamily = {
  readonly fontFamily: string;
  readonly fontDefinitions: readonly NativeFontDefinition[];
};

export const fiticianFontManifest = {
  android: [
    {
      fontDefinitions: [
        { path: "./assets/fonts/Vazirmatn-Regular.ttf", weight: 400 },
        { path: "./assets/fonts/Vazirmatn-Medium.ttf", weight: 500 },
        { path: "./assets/fonts/Vazirmatn-SemiBold.ttf", weight: 600 },
        { path: "./assets/fonts/Vazirmatn-Bold.ttf", weight: 700 },
        { path: "./assets/fonts/Vazirmatn-ExtraBold.ttf", weight: 800 },
      ],
      fontFamily: "Vazirmatn",
    },
    {
      fontDefinitions: [
        { path: "./assets/fonts/Lalezar-Regular.otf", weight: 400 },
      ],
      fontFamily: "Lalezar",
    },
    {
      fontDefinitions: [
        { path: "./assets/fonts/Sora-Regular.otf", weight: 400 },
        { path: "./assets/fonts/Sora-SemiBold.otf", weight: 600 },
        { path: "./assets/fonts/Sora-Bold.otf", weight: 700 },
        { path: "./assets/fonts/Sora-ExtraBold.otf", weight: 800 },
      ],
      fontFamily: "Sora",
    },
  ] satisfies readonly NativeFontFamily[],
  ios: [
    "./assets/fonts/Vazirmatn-Regular.ttf",
    "./assets/fonts/Vazirmatn-Medium.ttf",
    "./assets/fonts/Vazirmatn-SemiBold.ttf",
    "./assets/fonts/Vazirmatn-Bold.ttf",
    "./assets/fonts/Vazirmatn-ExtraBold.ttf",
    "./assets/fonts/Lalezar-Regular.otf",
    "./assets/fonts/Sora-Regular.otf",
    "./assets/fonts/Sora-SemiBold.otf",
    "./assets/fonts/Sora-Bold.otf",
    "./assets/fonts/Sora-ExtraBold.otf",
  ] as const,
} as const;

export const fiticianFontFiles = fiticianFontManifest.ios;
