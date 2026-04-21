from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

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
class SenderInfo:
	name: str
	icon_url: str | None = None


@dataclass(kw_only=True)
class BaseMessage(ABC):
	provider: "ProviderType"
	user_id: str

	sender: SenderInfo | None = None

	metadata: dict | None = None

	@property
	@abstractmethod
	def type(self) -> "MessageType":
		"""Type of the message to match with Raven Message doctype."""

	@property
	@abstractmethod
	def provider_mapping(self) -> dict["ProviderType", Callable[["BaseMessage"], dict]]:
		"""Mapping of provider to a callable that converts the message to the provider format."""

	def to_provider(self) -> dict:
		if self.provider not in self.provider_mapping:
			raise NotImplementedError("Provider not implemented.")

		return self.provider_mapping[self.provider](self)


@dataclass(kw_only=True)
class FileUrl:
	url: str


@dataclass(kw_only=True)
class FileContent:
	file_name: str
	file_content: bytes


File = FileUrl | FileContent


# ---
# MESSAGE CLASSES IMPLEMEN
# ---


@dataclass(kw_only=True)
class TextMessage(BaseMessage):
	text: str

	@property
	def type(self) -> str:
		return "Text"

	def to_line(self) -> dict:
		return {
			"type": "text",
			"text": self.text,
		}

	def to_facebook(self) -> dict:
		return {
			"text": self.text,
		}

	def provider_mapping(self):
		return {
			"line": self.to_line,
			"facebook": self.to_facebook,
		}


@dataclass(kw_only=True)
class FileMessage(BaseMessage):
	file: File

	@property
	def type(self) -> str:
		return "File"

	def to_line(self) -> dict:
		if isinstance(self.file, FileUrl):
			return {
				"type": "file",
				"file": {
					"url": self.file.url,
				},
			}
		else:
			raise NotImplementedError("Line provider does not support file content.")

	def to_facebook(self) -> dict:
		if isinstance(self.file, FileUrl):
			return {
				"attachment": {
					"type": "file",
					"payload": {
						"url": self.file.url,
					},
				},
			}
		else:
			raise NotImplementedError("Facebook provider does not support file content.")

	def provider_mapping(self):
		return {
			"line": self.to_line,
			"facebook": self.to_facebook,
		}


@dataclass(kw_only=True)
class ImageMessage(FileMessage):
	pass
