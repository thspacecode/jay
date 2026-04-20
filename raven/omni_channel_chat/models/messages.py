from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class StdMessage(ABC):
	user_id: str
	metadata: dict

	@property
	@abstractmethod
	def type(self) -> str:
		pass


@dataclass
class TextMessage(StdMessage):
	text: str

	@property
	def type(self) -> str:
		return "Text"


@dataclass
class FileMessage(StdMessage):
	file_name: str
	file_content: bytes

	@property
	def type(self) -> str:
		return "File"


@dataclass
class ImageMessage(StdMessage):
	file_name: str
	file_content: bytes

	@property
	def type(self) -> str:
		return "Image"
