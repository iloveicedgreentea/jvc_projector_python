class ConnectionClosedError(Exception):
    pass


class CommandTimeoutError(Exception):
    pass


class BlankMessageError(Exception):
    pass


class CommandRetryExceededError(Exception):
    pass
