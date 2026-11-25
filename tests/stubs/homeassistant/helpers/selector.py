class _Cfg(dict):
    def __init__(self, **kw): super().__init__(**kw)
SelectSelectorConfig = EntitySelectorConfig = NumberSelectorConfig = _Cfg
class SelectSelectorMode: LIST = "list"; DROPDOWN = "dropdown"
class NumberSelectorMode: BOX = "box"
def SelectOptionDict(value, label): return {"value": value, "label": label}
class _Sel:
    def __init__(self, config=None): self.config = config
class SelectSelector(_Sel):
    """Contrôles faits par Home Assistant (SelectSelector.CONFIG_SCHEMA)."""
    def __init__(self, config=None):
        super().__init__(config)
        for k, v in (config or {}).items():
            if v is None:
                raise ValueError(f"SelectSelectorConfig: {k}=None refusé par Home Assistant")
        if "translation_key" in config and not isinstance(config["translation_key"], str):
            raise ValueError("translation_key doit être un texte")
        for o in config.get("options", []):
            ok = isinstance(o, str) or (isinstance(o, dict) and isinstance(o.get("value"), str) and isinstance(o.get("label"), str))
            if not ok:
                raise ValueError(f"option invalide pour Home Assistant : {o!r}")
class NumberSelector(_Sel):
    def __init__(self, config=None):
        super().__init__(config)
        for k, v in (config or {}).items():
            if v is None:
                raise ValueError(f"NumberSelectorConfig: {k}=None refusé par Home Assistant")
EntitySelector = TimeSelector = BooleanSelector = _Sel
