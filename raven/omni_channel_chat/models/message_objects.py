from typing import Any

# Plain dict type alias for outgoing message objects.
# Keys: text (str), sender (dict | None) with keys name (str | None), icon_url (str | None)
MessageObjects = dict[str, Any]
