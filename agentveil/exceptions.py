"""AVP SDK exceptions — clear, actionable error messages."""


class AVPError(Exception):
    """Base exception for all AVP SDK errors."""

    def __init__(self, message: str, status_code: int = 0, detail: str = ""):
        self.message = message
        self.status_code = status_code
        self.detail = detail
        super().__init__(message)


class AVPAuthError(AVPError):
    """Authentication failed — invalid signature, expired timestamp, or nonce reuse."""
    pass


class AVPNotFoundError(AVPError):
    """Resource not found — agent, card, escrow, etc."""
    pass


class AVPRateLimitError(AVPError):
    """Rate limit exceeded — wait and retry."""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(message, status_code=429)


class AVPValidationError(AVPError):
    """Invalid input data."""
    pass


class AVPServerError(AVPError):
    """Server-side error — retry later."""
    pass
