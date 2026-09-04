import { useCallback, useEffect, useRef } from "react";

export const AUTO_ADVANCE_DELAY_MS = 140;

export function useAutoAdvance(delayMs = AUTO_ADVANCE_DELAY_MS) {
  const isAdvancingRef = useRef(false);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current !== null) {
        window.clearTimeout(timerRef.current);
      }
    };
  }, []);

  const selectAndAdvance = useCallback((onSelect: () => void, onAdvance: () => void) => {
    if (isAdvancingRef.current) return;
    isAdvancingRef.current = true;
    onSelect();
    timerRef.current = window.setTimeout(() => {
      onAdvance();
      isAdvancingRef.current = false;
    }, delayMs);
  }, [delayMs]);

  const resetAdvancing = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    isAdvancingRef.current = false;
  }, []);

  return { selectAndAdvance, resetAdvancing, isAdvancingRef };
}
