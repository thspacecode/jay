from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from raven.omni_channel_chat.webhook_handler import handle_incoming_webhook_message

if TYPE_CHECKING:
	from raven.omni_channel_chat.doctype.omni_channel_chat_provider.omni_channel_chat_provider import (
		OmniChannelChatProvider,
	)


class Provider[ProviderWebhookEvent, ProviderMessageObject](ABC):
	provider_config: "OmniChannelChatProvider"

	def __init__(self, config: "OmniChannelChatProvider"):
		self.provider_config = config
		self.provider_config.decode_password_field()

	async def push_message_to_raven(self, messages: list[dict]) -> None:
		for message in messages:
			await handle_incoming_webhook_message(
				provider=self,
				message=message,
			)

	async def handle_webhook(self, body: bytes, headers: dict) -> None:
		messages = await self.extract_messages(body=body, headers=headers)
		await self.push_message_to_raven(messages=messages)

	@abstractmethod
	async def get_user_info(self, user_id: str) -> dict:
		"""Fetch user info from the provider's platform."""

	@abstractmethod
	async def show_typing(self, user_id: str) -> None:
		"""Show a typing / loading indicator."""

	@abstractmethod
	async def send_reply(self, user_id: str, message: dict, context: Any) -> None:
		"""Send a chat response back within the webhook reply context."""

	@abstractmethod
	async def send_message(self, user_id: str, message: dict) -> None:
		"""Send an outbound message (push, not reply)."""

	@abstractmethod
	async def event_mapper(self, event: ProviderWebhookEvent) -> dict | None:
		"""Map a provider-specific webhook event into a standardized event. Return None to skip."""

	@abstractmethod
	async def standardize_events(self, events: list[ProviderWebhookEvent]) -> list[dict]:
		"""Standardize a list of provider-specific webhook events into standardized events."""

	@abstractmethod
	async def extract_messages(self, body: bytes, headers: dict) -> list[dict]:
		"""Parse the raw webhook body into standardized messages."""
