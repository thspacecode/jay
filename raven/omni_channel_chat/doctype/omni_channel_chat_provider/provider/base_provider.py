from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Callable, Generic, TypeVar

from werkzeug.wrappers import Response

from raven.omni_channel_chat.models.message import (
	ChatDestination,
	FileContent,
	StdInboundEvent,
	StdMessage,
	UserDisplay,
)

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
		self,
		body: bytes,
		headers: dict,
		callback: Callable[[ChatDestination, str, StdMessage], None],
	) -> Response:
		for e in self.extract_messages(body=body, headers=headers):
			callback(e.destination, e.sender_id, e.message)
		return Response("ok", status=200, content_type="text/plain")

	@abstractmethod
	def handle_frappe_api(
		self, callback: Callable[[ChatDestination, str, StdMessage], None]
	) -> Response:
		"""Extract data from frappe request and pass to `handle_webhook`."""

	@abstractmethod
	def get_user_info(self, user_id: str, destination: "ChatDestination") -> UserDisplay:
		"""Fetch user display info from the provider's platform."""

	@abstractmethod
	def download_attachment(self, url: str, file_name: str | None = None) -> FileContent:
		"""Download a file from the given URL and return its content and a file name."""

	@abstractmethod
	def show_typing(self, destination_id: str) -> None:
		"""Show a typing / loading indicator."""

	@abstractmethod
	def send_reply(self, destination_id: str, message: StdMessage) -> None:
		"""Send a chat response back within the webhook reply context."""

	@abstractmethod
	def send_message(self, destination_id: str, message: StdMessage) -> None:
		"""Send an outbound message (push)."""

	@abstractmethod
	def event_mapper(self, event: ProviderWebhookEvent) -> StdInboundEvent | None:
		"""Map a provider-specific webhook event into a standardized inbound event. Return None to skip."""

	@abstractmethod
	def standardize_events(self, events: list[ProviderWebhookEvent]) -> list[StdInboundEvent]:
		"""Standardize a list of provider-specific webhook events into StdInboundMessage tuples."""

	@abstractmethod
	def extract_messages(self, body: bytes, headers: dict) -> list[StdInboundEvent]:
		"""Parse the raw webhook body into standardized inbound events."""
