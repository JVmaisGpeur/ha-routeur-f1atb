class _Cfg(dict):
    def __init__(self, **kw): super().__init__(**kw)
SelectSelectorConfig = EntitySelectorConfig = NumberSelectorConfig = _Cfg
class SelectSelectorMode: LIST = "list"; DROPDOWN = "dropdown"
class NumberSelectorMode: BOX = "box"
def SelectOptionDict(value, label): return {"value": value, "label": label}
class _Sel:
    def __init__(self, config=None): self.config = config
SelectSelector = EntitySelector = NumberSelector = TimeSelector = BooleanSelector = _Sel
