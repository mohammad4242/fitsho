export interface QuestionProgress {
  readonly current: number;
  readonly progress: number;
  readonly total: number;
}

export function nextQuestionIndex(current: number, total: number): number {
  return Math.min(Math.max(0, total - 1), current + 1);
}

export function previousQuestionIndex(current: number): number {
  return Math.max(0, current - 1);
}

export function getQuestionProgress(current: number, total: number): QuestionProgress {
  const safeTotal = Math.max(1, total);
  const safeCurrent = Math.min(Math.max(0, current), safeTotal - 1);
  return {
    current: safeCurrent + 1,
    progress: (safeCurrent + 1) / safeTotal,
    total: safeTotal,
  };
}
