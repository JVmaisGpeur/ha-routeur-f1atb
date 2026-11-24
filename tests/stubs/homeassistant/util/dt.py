import datetime as _d
UTC = _d.timezone.utc
NOW = [None]
def now():
    return NOW[0] or _d.datetime.now(UTC)
def utcnow():
    return (NOW[0] or _d.datetime.now(UTC)).astimezone(UTC)
