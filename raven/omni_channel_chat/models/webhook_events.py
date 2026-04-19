from typing import Any

# Plain dict type aliases for standardized webhook events.
# These replace the previous Pydantic models.

# {"type": str, "text": str}
StdTextMessage = dict[str, Any]

# {"provider": str, "user_id": str, "message": StdTextMessage, "message_metadata": dict}
StdWebhookEvent = dict[str, Any]

# Alias kept for backwards compatibility
StdMessageEvent = StdWebhookEvent
