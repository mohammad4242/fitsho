import { useCallback, useEffect, useRef } from "react";

export const PUBLIC_AUTO_ADVANCE_DELAY_MS = 140;

export function usePublicAutoAdvance() {
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const resetAdvancing = useCallback(() => {
    if (timer.current !== null) {
      clearTimeout(timer.current);
      timer.current = null;
    }
  }, []);

  const selectAndAdvance = useCallback(
    (select: () => void, advance: () => void) => {
      resetAdvancing();
      select();
      timer.current = setTimeout(() => {
        timer.current = null;
        advance();
      }, PUBLIC_AUTO_ADVANCE_DELAY_MS);
    },
    [resetAdvancing],
  );

  useEffect(() => resetAdvancing, [resetAdvancing]);

  return { resetAdvancing, selectAndAdvance };
}
