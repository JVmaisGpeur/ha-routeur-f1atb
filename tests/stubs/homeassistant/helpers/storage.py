class Store:
    def __init__(self, hass, version, key): self.saved = None
    async def async_load(self): return None
    async def async_save(self, data): self.saved = dict(data)
