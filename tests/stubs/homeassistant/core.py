class _State:
    def __init__(self, state, attributes=None): self.state = state; self.attributes = attributes or {}
class _States(dict):
    def get(self, k): return dict.get(self, k)
class _Bus:
    def __init__(self): self.events = []
    def async_fire(self, name, data=None): self.events.append((name, data))
class HomeAssistant:
    def __init__(self): self.states = _States(); self.bus = _Bus(); self.data = {}
def callback(f): return f
