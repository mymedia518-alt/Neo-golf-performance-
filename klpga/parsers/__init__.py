class ParseError(Exception):
    """Raised when an HTML page does not contain the expected structure.

    Adapters treat this as a signal that the page may be JS-rendered (or
    that the site markup changed) and should try the Playwright fallback.
    """
