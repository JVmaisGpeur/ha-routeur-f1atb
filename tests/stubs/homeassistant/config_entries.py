class ConfigEntry:
    def __init__(self, data, options=None, entry_id="e1", unique_id="aa:bb"):
        self.data = data; self.options = options or {}; self.entry_id = entry_id; self.unique_id = unique_id; self.title = "T"
