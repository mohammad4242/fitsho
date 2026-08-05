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


class NutritionProductModeError(Exception):
    pass
