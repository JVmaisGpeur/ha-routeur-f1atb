SOURCE_INTEGRATION_DISCOVERY = "integration_discovery"
class ConfigEntry:
    def __init__(self, data, options=None, entry_id="e1", unique_id="aa:bb"):
        self.data = data; self.options = options or {}; self.entry_id = entry_id; self.unique_id = unique_id; self.title = "T"
ConfigFlowResult = dict
class AbortFlow(Exception):
    def __init__(self, reason): super().__init__(reason); self.reason = reason
class _Flow:
    def __init__(self, *a, **k): pass
    def async_show_form(self, step_id, data_schema=None, errors=None, description_placeholders=None):
        return {"type": "form", "step_id": step_id, "schema": data_schema, "errors": errors or {}, "placeholders": description_placeholders}
    def async_show_menu(self, step_id, menu_options):
        return {"type": "menu", "step_id": step_id, "menu_options": menu_options}
    def async_create_entry(self, title, data, options=None):
        return {"type": "create_entry", "title": title, "data": data, "options": options}
    def async_abort(self, reason): return {"type": "abort", "reason": reason}
class ConfigFlow(_Flow):
    def __init_subclass__(cls, domain=None, **kw): super().__init_subclass__(**kw)
    context = {}
    async def async_set_unique_id(self, uid, *, raise_on_progress=True): self.unique_id = uid; self.raise_on_progress = raise_on_progress
    def _abort_if_unique_id_configured(self, updates=None): pass
    def _async_current_entries(self, include_ignore=True): return []
    def _async_abort_entries_match(self, match): pass
class OptionsFlow(_Flow):
    pass
