"""Domain errors. Every error leaves the API as {"detail": {"code", "message"}}."""


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def not_found(code: str, message: str) -> AppError:
    return AppError(404, code, message)
