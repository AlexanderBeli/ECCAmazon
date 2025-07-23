"""Custom application-wide exceptions."""


class ApplicationError(Exception):
    """Base class for application-specific errors."""

    def __init__(
        self, message: str = "An application error occurred", original_exception: Exception | None = None
    ) -> None:
        super().__init__(message)
        self.original_exception = original_exception
        self.message = message

    def __str__(self) -> str:
        if self.original_exception:
            return f"{self.message} (Original error: {self.original_exception})"
        return self.message


class APIError(ApplicationError):
    """Exception raised for errors during external API calls."""

    def __init__(
        self,
        message: str = "API call failed",
        original_exception: Exception | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message, original_exception)
        self.status_code = status_code
        self.message = f"API Error: {message}"
        if status_code:
            self.message += f" (Status Code: {status_code})"


class DatabaseError(ApplicationError):
    """Exception raised for errors during database operations."""

    def __init__(self, message: str = "Database operation failed", original_exception: Exception | None = None) -> None:
        super().__init__(message, original_exception)
        self.message = f"Database Error: {message}"
