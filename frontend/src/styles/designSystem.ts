export function applyDesignSystem(documentElement: HTMLElement) {
  documentElement.classList.add("fitsho-app");
  documentElement.dataset.fitshoTheme = "dark";
}
