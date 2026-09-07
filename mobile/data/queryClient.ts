import { QueryClient } from "@tanstack/react-query";

import { mobileQueryDefaults } from "../platform/queryDefaults";

export function createMobileQueryClient(): QueryClient {
  return new QueryClient({ defaultOptions: mobileQueryDefaults });
}
