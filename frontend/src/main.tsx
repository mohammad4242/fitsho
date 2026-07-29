import "@fontsource/lalezar";
import "@fontsource-variable/sora";
import "@fontsource-variable/vazirmatn";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import "./i18n";
import "./index.css";
import { applyDesignSystem } from "./styles/designSystem";

applyDesignSystem(document.documentElement);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
