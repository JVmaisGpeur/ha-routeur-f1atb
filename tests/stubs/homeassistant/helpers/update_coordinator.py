class UpdateFailed(Exception):
    pass
class DataUpdateCoordinator:
    def __class_getitem__(cls, item): return cls
    def __init__(self, hass, logger, name=None, update_interval=None):
        self.hass = hass; self.data = None; self.last_update_success = True
    async def async_request_refresh(self): pass
    def async_update_listeners(self): pass
