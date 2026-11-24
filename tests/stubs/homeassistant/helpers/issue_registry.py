ISSUES = {}
class IssueSeverity:
    WARNING = "warning"
def async_create_issue(hass, domain, issue_id, **kw): ISSUES[issue_id] = kw
def async_delete_issue(hass, domain, issue_id): ISSUES.pop(issue_id, None)
