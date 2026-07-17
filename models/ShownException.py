class ShownException(Exception):
    prefix = "Error"

    def __init__(self, message: str):
        super().__init__(f"{self.prefix}: {message}")

class BadRequestException(ShownException):
    prefix = "Bad Request"

class NotFoundException(ShownException):
    prefix = "Not Found"

class UnauthorizedException(ShownException):
    prefix = "Unauthorized"

class BadStateException(ShownException):
    prefix = "Bad State"
