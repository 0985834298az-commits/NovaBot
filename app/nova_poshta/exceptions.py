"""Nova Poshta API exceptions."""


class NovaPoshtaError(Exception):
    """Base exception for Nova Poshta integration."""


class NovaPoshtaTransportError(NovaPoshtaError):
    """Raised when the HTTP request to Nova Poshta fails."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class NovaPoshtaResponseError(NovaPoshtaError):
    """Raised when the Nova Poshta response cannot be parsed or is invalid."""


class NovaPoshtaApiError(NovaPoshtaError):
    """Raised when Nova Poshta returns success=false."""

    def __init__(self, message: str, *, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.errors = errors or []
