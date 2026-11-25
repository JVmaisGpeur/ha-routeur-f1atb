class _Reg:
    def async_get_device(self, identifiers=None): return None
def async_get(hass): return _Reg()
def format_mac(m): return m.lower()
