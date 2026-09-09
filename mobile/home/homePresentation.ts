export type HomeHeroLayout = "split" | "stacked";

export function getHomeHeroLayout(screenWidth: number): HomeHeroLayout {
  return screenWidth < 350 ? "stacked" : "split";
}

export function getQuickActionColumns(screenWidth: number): 1 | 2 {
  return screenWidth < 350 ? 1 : 2;
}
