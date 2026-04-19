from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from raven.omni_channel_chat.webhook_handler import WebhookHandler

if TYPE_CHECKING:
	from raven.omni_channel_chat.doctype.omni_channel_chat_provider.omni_channel_chat_provider import (
		OmniChannelChatProvider,
	)


class Provider[ProviderWebhookEvent, ProviderMessageObject](ABC):
	provider_config: "OmniChannelChatProvider"

	def __init__(self, config: "OmniChannelChatProvider"):
		self.provider_config = config
		self.provider_config.decode_password_field()

	def push_message_to_raven(self, messages: list[dict]) -> None:
		handler = WebhookHandler(provider=self)
		for message in messages:
			handler.handle(message)

	def handle_webhook(self, body: bytes, headers: dict) -> None:
		messages = self.extract_messages(body=body, headers=headers)
		self.push_message_to_raven(messages=messages)

	@abstractmethod
	def get_user_info(self, user_id: str) -> dict:
		"""Fetch user info from the provider's platform."""

	@abstractmethod
	def show_typing(self, user_id: str) -> None:
		"""Show a typing / loading indicator."""

	@abstractmethod
	def send_reply(self, user_id: str, message: dict, context: Any) -> None:
		"""Send a chat response back within the webhook reply context."""

	@abstractmethod
	def send_message(self, user_id: str, message: dict) -> None:
		"""Send an outbound message (push, not reply)."""

	@abstractmethod
	def event_mapper(self, event: ProviderWebhookEvent) -> dict | None:
		"""Map a provider-specific webhook event into a standardized event. Return None to skip."""

	@abstractmethod
	def standardize_events(self, events: list[ProviderWebhookEvent]) -> list[dict]:
		"""Standardize a list of provider-specific webhook events into standardized events."""

	@abstractmethod
	def extract_messages(self, body: bytes, headers: dict) -> list[dict]:
		"""Parse the raw webhook body into standardized messages."""
