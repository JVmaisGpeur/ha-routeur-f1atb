class ClientError(Exception):
    pass
class ClientSession:
    pass
class ClientTimeout:
    def __init__(self, total=None): self.total = total
