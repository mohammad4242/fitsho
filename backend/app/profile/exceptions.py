class ProfileAlreadyExistsError(Exception):
    pass


class ProfileNotFoundError(Exception):
    pass


class ProfileInvariantError(Exception):
    pass


class InvalidWorkoutSetupError(Exception):
    pass


class AgeNotSupportedError(Exception):
    pass


class AgeOutOfRangeError(Exception):
    pass
