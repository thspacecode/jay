from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class StdMessage(ABC):
	user_id: str
	metadata: dict

	@abstractmethod
	def to_raven(self) -> dict:
		pass


@dataclass
class TextMessage(StdMessage):
	text: str

	def to_raven(self):
		return {
			"type": "Text",
			"text": self.text,
		}


@dataclass
class FileMessage(StdMessage):
	file_name: str
	file_content: bytes

	def to_raven(self):
		return {
			"type": "File",
			"file_name": self.file_name,
			"file_content": self.file_content,
		}


@dataclass
class ImageMessage(StdMessage):
	file_name: str
	file_content: bytes

	def to_raven(self):
		return {
			"type": "Image",
			"file_name": self.file_name,
			"file_content": self.file_content,
		}
