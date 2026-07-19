class ShownException(Exception):
    prefix = "Error"

    def __init__(
        self,
        content: str,
        **msg
    ):
        self.data = msg
        msg["content"] = f"{self.prefix}: {content}"

        super().__init__(msg["content"])

class BadRequestException(ShownException):
    prefix = "Bad Request"

class NotFoundException(ShownException):
    prefix = "Not Found"

class UnauthorizedException(ShownException):
    prefix = "Unauthorized"

class BadStateException(ShownException):
    prefix = "Bad State"
