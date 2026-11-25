UNDEFINED = object()
class _Marker:
    def __init__(self, key, default=UNDEFINED, description=None):
        self.schema = key; self.default = default; self.description = description
    def __hash__(self): return hash(self.schema)
    def __eq__(self, o): return getattr(o, "schema", o) == self.schema
class Required(_Marker): pass
class Optional(_Marker): pass
class Schema:
    def __init__(self, schema): self.schema = schema
    def extend(self, other): d = dict(self.schema); d.update(other); return Schema(d)
    def keys(self): return [k.schema for k in self.schema]
def All(*a): return a
def Coerce(t): return t
def Range(**k): return k
def In(x): return x
def Length(**k): return k
