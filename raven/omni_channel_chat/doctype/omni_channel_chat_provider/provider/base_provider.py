from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Callable, Generic, TypeVar

from werkzeug.wrappers import Response

from raven.omni_channel_chat.models.message import BaseMessage, FileContent, UserInfo

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

	def handle_webhook(
		self, body: bytes, headers: dict, callback: Callable[[BaseMessage], None]
	) -> Response:
		messages = self.extract_messages(body=body, headers=headers)
		for message in messages:
			callback(message)
		return Response("ok", status=200, content_type="text/plain")

	@abstractmethod
	def handle_frappe_api(self, callback: Callable[[BaseMessage], None]) -> Response:
		"""Extract data from frappe request and pass to `handle_webhook`."""

	@abstractmethod
	def get_user_info(self, user_id: str) -> UserInfo:
		"""Fetch user info from the provider's platform."""

	@abstractmethod
	def download_attachment(self, url: str, file_name: str | None = None) -> FileContent:
		"""Download a file from the given URL and return its content and a file name."""

	@abstractmethod
	def show_typing(self, user_id: str) -> None:
		"""Show a typing / loading indicator."""

	@abstractmethod
	def send_reply(self, message: BaseMessage) -> None:
		"""Send a chat response back within the webhook reply context."""

	@abstractmethod
	def send_message(self, message: BaseMessage) -> None:
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
