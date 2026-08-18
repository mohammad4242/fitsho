class ProfileAlreadyExistsError(Exception):
    pass


class ProfileNotFoundError(Exception):
    pass


class ProfileCycleNotFoundError(Exception):
    pass


class ProfileInvariantError(Exception):
    pass


class InvalidWorkoutSetupError(Exception):
    pass


class InvalidProfilePreferencesError(Exception):
    pass


class AgeNotSupportedError(Exception):
    pass


class AgeOutOfRangeError(Exception):
    pass
