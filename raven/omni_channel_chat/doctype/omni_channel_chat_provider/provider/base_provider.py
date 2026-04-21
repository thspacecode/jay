from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from werkzeug.wrappers import Response

from raven.omni_channel_chat.models.message import BaseMessage
from raven.omni_channel_chat.omni_channel_raven_connector import OmniChannelRavenConnector

if TYPE_CHECKING:
	from raven.omni_channel_chat.doctype.omni_channel_chat_provider.omni_channel_chat_provider import (
		OmniChannelChatProvider,
	)

ProviderWebhookEvent = TypeVar("ProviderWebhookEvent")


class Provider(ABC, Generic[ProviderWebhookEvent]):
	provider_config: "OmniChannelChatProvider"

	def __init__(self, config: "OmniChannelChatProvider"):
		self.provider_config = config
		self.provider_config.decode_password_field()

	def push_message_to_raven(self, messages: list[BaseMessage]) -> None:
		handler = OmniChannelRavenConnector(provider=self)
		for message in messages:
			handler.receive_from_provider(message)

	def handle_webhook(self, body: bytes, headers: dict) -> Response:
		messages = self.extract_messages(body=body, headers=headers)
		self.push_message_to_raven(messages=messages)
		return Response("ok", status=200, content_type="text/plain")

	@abstractmethod
	def handle_frappe_api(self) -> Response:
		"""Extract data from frappe request and pass to `handle_webhook`."""

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
	def event_mapper(self, event: ProviderWebhookEvent) -> BaseMessage | None:
		"""Map a provider-specific webhook event into a standardized message. Return None to skip."""

	@abstractmethod
	def standardize_events(self, events: list[ProviderWebhookEvent]) -> list[BaseMessage]:
		"""Standardize a list of provider-specific webhook events into BaseMessage instances."""

	@abstractmethod
	def extract_messages(self, body: bytes, headers: dict) -> list[BaseMessage]:
		"""Parse the raw webhook body into standardized messages."""
