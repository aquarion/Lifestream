class DestinyException(Exception):
    pass


class DestinyAccountNotFound(DestinyException):
    pass

class DestinyThrottledByGameServer(DestinyException):
    pass