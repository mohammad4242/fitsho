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
