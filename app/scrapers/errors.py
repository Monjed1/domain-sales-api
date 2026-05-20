class ScraperError(Exception):
    """Base error for marketplace scrapers."""


class DropDaxRateLimitError(ScraperError):
    """DropDax returned 429 Too Many Requests."""

    def __init__(
        self,
        message: str = (
            "DropDax rate limit reached (429). Wait a few minutes, use a shorter "
            "period (day/week), or try again later."
        ),
    ) -> None:
        super().__init__(message)


class DropDaxUpstreamError(ScraperError):
    """DropDax or CDN returned a transient server error."""

    def __init__(
        self,
        message: str = "DropDax is temporarily unavailable. Please retry shortly.",
    ) -> None:
        super().__init__(message)
