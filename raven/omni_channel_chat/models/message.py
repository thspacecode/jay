from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from linebot.v3.messaging import (
	ImageMessage as LineImageMessage,
)
from linebot.v3.messaging import (
	Sender as LineSender,
)
from linebot.v3.messaging import (
	TextMessageV2 as LineTextMessage,
)

if TYPE_CHECKING:
	from raven.omni_channel_chat.doctype.omni_channel_chat_provider.omni_channel_chat_provider import (
		OmniChannelChatProvider,
	)
	from raven.raven_messaging.doctype.raven_message.raven_message import RavenMessage

	ProviderType = OmniChannelChatProvider.provider
	MessageType = RavenMessage.message_type

# ---
# BASE MESSAGE CLASSES
# ---


@dataclass(kw_only=True)
class UserInfo:
	user_id: str
	display_name: str
	picture_url: str | None = None


@dataclass(kw_only=True)
class SenderInfo:
	name: str
	icon_url: str | None = None


# ---
# PROVIDER MESSAGE MIXIN
# ---


class LineMessageMixin:
	sender: "SenderInfo | None"

	def build_line_sender(self) -> LineSender | None:
		if self.sender is not None:
			return LineSender(name=self.sender.name, iconUrl=self.sender.icon_url)
		return None


@dataclass(kw_only=True)
class BaseMessage(ABC, LineMessageMixin):
	provider: "ProviderType"

	provider_id: str
	user_id: str

	sender: SenderInfo | None = None

	metadata: dict | None = None

	@property
	@abstractmethod
	def type(self) -> "MessageType":
		"""Type of the message to match with Raven Message doctype."""

	@property
	@abstractmethod
	def provider_mapping(self) -> dict["ProviderType", Callable[[], dict]]:
		"""Mapping of provider to a callable that converts the message to the provider format."""

	def to_provider(self) -> Any:
		if self.provider not in self.provider_mapping:
			raise NotImplementedError("Provider not implemented.")

		return self.provider_mapping[self.provider]()


@dataclass(kw_only=True)
class FileUrl:
	url: str


@dataclass(kw_only=True)
class FileContent:
	file_name: str
	file_content: bytes


File = FileUrl | FileContent


# ---
# MESSAGE CLASSES
# ---


@dataclass(kw_only=True)
class TextMessage(BaseMessage):
	text: str

	@property
	def type(self):
		return "Text"

	def to_line(self):
		return LineTextMessage(text=self.text, sender=self.build_line_sender())

	def to_facebook(self):
		return {"text": self.text}

	@property
	def provider_mapping(self):
		return {
			"line": self.to_line,
			"facebook": self.to_facebook,
		}


@dataclass(kw_only=True)
class FileMessage(BaseMessage):
	file: File

	@property
	def type(self):
		return "File"

	def to_line(self):
		if isinstance(self.file, FileUrl):
			return LineTextMessage(
				text="File: {url}",
				substitution={"url": self.file.url},
				sender=self.build_line_sender(),
			)
		raise NotImplementedError("Line provider does not support file content.")

	def to_facebook(self):
		if isinstance(self.file, FileUrl):
			return {
				"attachment": {
					"type": "file",
					"payload": {"url": self.file.url, "is_reusable": True},
				}
			}
		raise NotImplementedError("Facebook provider does not support file content.")

	@property
	def provider_mapping(self):
		return {
			"line": self.to_line,
			"facebook": self.to_facebook,
		}


@dataclass(kw_only=True)
class ImageMessage(BaseMessage):
	file: File

	@property
	def type(self):
		return "Image"

	def to_line(self):
		if isinstance(self.file, FileUrl):
			return LineImageMessage(
				original_content_url=self.file.url,
				preview_image_url=self.file.url,
				sender=self.build_line_sender(),
			)
		raise NotImplementedError("Line provider does not support file content.")

	def to_facebook(self):
		if isinstance(self.file, FileUrl):
			return {
				"attachment": {
					"type": "image",
					"payload": {"url": self.file.url, "is_reusable": True},
				}
			}
		raise NotImplementedError("Facebook provider does not support file content.")

	@property
	def provider_mapping(self):
		return {
			"line": self.to_line,
			"facebook": self.to_facebook,
		}
