class SharedProfileRequiredError(Exception):
    pass


class SafetyScreenRequiredError(Exception):
    pass


class NutritionProfileNotFoundError(Exception):
    pass


class SafetyDecisionNotFoundError(Exception):
    pass


class NutritionOnboardingBlockedError(Exception):
    pass


class StructuredExerciseRequiredError(Exception):
    pass


class StructuredExerciseNotFoundError(Exception):
    pass


class NutritionEstimateNotFoundError(Exception):
    pass


class NutritionEstimateBlockedError(Exception):
    pass


class GoalReselectionRequiredDomainError(Exception):
    pass


class NutritionTargetInfeasibleDomainError(Exception):
    def __init__(self, reason_codes: tuple[str, ...]) -> None:
        self.reason_codes = reason_codes


class NutritionProductModeError(Exception):
    pass


class ScheduledTemplateUnavailableError(Exception):
    def __init__(self, meal_id: str, category: str) -> None:
        self.meal_id = meal_id
        self.category = category
        super().__init__(f"{meal_id}:{category}")
