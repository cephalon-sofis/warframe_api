class LoginError(Exception):
    def __init__(self, text, code):
        self.text = text
        self.code = code

    def __str__(self):
        return self.text

class NotLoggedInException(Exception):
    pass

class AlreadyLoggedInException(LoginError):
    def __init__(self):
        super().__init__('Already logged in', 409)

class VersionOutOfDateException(LoginError):
    def __init__(self):
        super().__init__('Version out of date', 400)

class RecipeAlreadyStartedException(Exception):
    pass

class RecipeNotStartedException(Exception):
    pass

class RecipeNotFinishedException(Exception):
    pass

class ExtractorAlreadyDeployedException(Exception):
    pass

class ExtractorNotDeployedException(Exception):
    pass

class ExtractorNotFinishedException(Exception):
    pass
