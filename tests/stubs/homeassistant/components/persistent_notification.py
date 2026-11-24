CREATED = []
def async_create(hass, message, title=None, notification_id=None):
    CREATED.append((notification_id, message))
def async_dismiss(hass, notification_id):
    pass
