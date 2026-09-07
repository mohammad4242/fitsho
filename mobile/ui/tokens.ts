export type FiticianTokens = {
  readonly colors: {
    readonly canvas: string;
    readonly petrol: string;
    readonly teal: string;
    readonly surface: string;
    readonly surfaceSubtle: string;
    readonly surfaceRaised: string;
    readonly surfaceInteractive: string;
    readonly aqua: string;
    readonly blue: string;
    readonly coral: string;
    readonly amber: string;
    readonly success: string;
    readonly danger: string;
    readonly mist: string;
    readonly ink: string;
    readonly muted: string;
    readonly line: string;
    readonly lineStrong: string;
  };
  readonly spacing: Readonly<Record<1 | 2 | 3 | 4 | 5 | 6 | 7 | 8, number>>;
  readonly radii: {
    readonly small: number;
    readonly medium: number;
    readonly large: number;
    readonly extraLarge: number;
    readonly card: number;
    readonly pill: number;
  };
  readonly typography: {
    readonly fontFamily: {
      readonly bodyEnglish: string;
      readonly bodyPersian: string;
      readonly displayEnglish: string;
      readonly displayPersian: string;
    };
    readonly fontSize: Readonly<Record<"xs" | "sm" | "body" | "lg" | "h3" | "h2" | "h1", number>>;
    readonly lineHeight: Readonly<Record<"tight" | "body" | "loose", number>>;
    readonly fontWeight: Readonly<Record<"regular" | "medium" | "bold" | "extraBold", string>>;
  };
  readonly shadows: {
    readonly card: NativeShadowToken;
    readonly soft: NativeShadowToken;
    readonly focus: NativeShadowToken;
    readonly glow: NativeShadowToken;
  };
  readonly motion: {
    readonly fastMs: number;
    readonly mediumMs: number;
    readonly easing: "easeOutCubic";
    readonly pressedScale: number;
  };
  readonly layout: {
    readonly screenPadding: number;
    readonly tabletPadding: number;
    readonly contentMaxWidth: number;
    readonly readingMaxWidth: number;
    readonly minimumTouchTarget: number;
  };
};

export type NativeShadowToken = {
  readonly color: string;
  readonly offset: { readonly width: number; readonly height: number };
  readonly opacity: number;
  readonly radius: number;
  readonly elevation: number;
};

export const fiticianTokens = {
  colors: {
    amber: "#f2b85b",
    aqua: "#50dfce",
    blue: "#3b82f6",
    canvas: "#020607",
    coral: "#f67859",
    danger: "#f67859",
    ink: "#e8f4f1",
    line: "rgba(232,244,241,0.12)",
    lineStrong: "rgba(80,223,206,0.28)",
    mist: "#e8f4f1",
    muted: "#94aba5",
    petrol: "#091817",
    success: "#66c89f",
    surface: "#081211",
    surfaceInteractive: "rgba(80,223,206,0.07)",
    surfaceRaised: "#101e1c",
    surfaceSubtle: "#050b0c",
    teal: "#0e201e",
  },
  layout: {
    contentMaxWidth: 1_312,
    minimumTouchTarget: 48,
    readingMaxWidth: 1_088,
    screenPadding: 16,
    tabletPadding: 32,
  },
  motion: {
    easing: "easeOutCubic",
    fastMs: 160,
    mediumMs: 260,
    pressedScale: 0.985,
  },
  radii: {
    card: 18,
    extraLarge: 24,
    large: 18,
    medium: 14,
    pill: 999,
    small: 10,
  },
  shadows: {
    card: {
      color: "#000000",
      elevation: 3,
      offset: { height: 2, width: 0 },
      opacity: 0.25,
      radius: 10,
    },
    focus: {
      color: "#000000",
      elevation: 4,
      offset: { height: 4, width: 0 },
      opacity: 0.24,
      radius: 18,
    },
    glow: {
      color: "#50dfce",
      elevation: 4,
      offset: { height: 2, width: 0 },
      opacity: 0.24,
      radius: 9,
    },
    soft: {
      color: "#000000",
      elevation: 2,
      offset: { height: 2, width: 0 },
      opacity: 0.22,
      radius: 8,
    },
  },
  spacing: {
    1: 4,
    2: 8,
    3: 12,
    4: 16,
    5: 24,
    6: 32,
    7: 48,
    8: 72,
  },
  typography: {
    fontFamily: {
      bodyEnglish: "Sora",
      bodyPersian: "Vazirmatn",
      displayEnglish: "Sora",
      displayPersian: "Lalezar",
    },
    fontSize: {
      body: 16,
      h1: 32,
      h2: 24,
      h3: 20,
      lg: 18,
      sm: 14,
      xs: 12,
    },
    fontWeight: {
      bold: "700",
      extraBold: "800",
      medium: "500",
      regular: "400",
    },
    lineHeight: {
      body: 1.5,
      loose: 1.85,
      tight: 1.15,
    },
  },
} as const satisfies FiticianTokens;
