"""Domain errors raised by services; mapped to HTTP responses in main.py."""


class NotFoundError(Exception):
    """Requested job/certificate/file does not exist -> 404."""


class NotReadyError(Exception):
    """Resource exists but isn't downloadable yet (pending or failed) -> 409."""
