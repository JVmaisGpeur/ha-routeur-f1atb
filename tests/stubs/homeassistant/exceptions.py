class ServiceValidationError(Exception):
    def __init__(self, *a, translation_domain=None, translation_key=None, translation_placeholders=None):
        super().__init__(translation_key); self.translation_key = translation_key
