from typing import Any

import frappe
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
	ApiClient,
	Configuration,
	ImageMessage,
	Message,
	MessagingApi,
	MessagingApiBlob,
	PushMessageRequest,
	ReplyMessageRequest,
	ShowLoadingAnimationRequest,
	TextMessage,
)
from linebot.v3.messaging import (
	Sender as LineSender,
)
from linebot.v3.messaging import TextMessage as LineTextMessage
from linebot.v3.webhook import WebhookParser
from linebot.v3.webhooks import Event as LineEvent
from linebot.v3.webhooks import FileMessageContent, ImageMessageContent, TextMessageContent
from linebot.v3.webhooks import MessageEvent as LineMessageEvent

from . import Provider


class LineProvider(Provider[LineEvent, list[TextMessage]]):
	config: Configuration
	parser: WebhookParser

	def __init__(self, config):
		super().__init__(config=config)

		self.config = Configuration(
			access_token=self.provider_config.line_channel_access_token,
		)
		self.parser = WebhookParser(
			channel_secret=self.provider_config.line_channel_secret,
		)

	def handle_frappe_api(self):
		request = frappe.local.request
		body: bytes = request.get_data()
		headers: dict = dict(request.headers)
		return self.handle_webhook(body=body, headers=headers)

	def get_user_info(self, user_id: str) -> dict:
		with ApiClient(self.config) as api_client:
			profile = MessagingApi(api_client).get_profile(user_id)
			return {
				"user_id": profile.user_id,
				"display_name": profile.display_name,
				"picture_url": profile.picture_url,
			}

	def show_typing(self, user_id: str) -> None:
		with ApiClient(self.config) as api_client:
			MessagingApi(api_client).show_loading_animation(
				ShowLoadingAnimationRequest(chatId=user_id, loadingSeconds=60)
			)

	@staticmethod
	def _to_https(url: str) -> str:
		if url and url.startswith("http://"):
			return "https://" + url[7:]
		return url

	def _build_outbound_message(self, message: dict) -> Message:
		sender = None
		if message.get("sender"):
			sender = LineSender(
				name=message["sender"].get("name"),
				icon_url=message["sender"].get("icon_url"),
			)
		msg_type = message.get("type", "Text")
		if msg_type == "Image":
			file_url = self._to_https(message["file_url"])
			print(file_url)
			img_msg = ImageMessage(
				original_content_url=file_url,
				preview_image_url=file_url,
			)
			if sender:
				img_msg.sender = sender
			return img_msg
		# File falls back to a text link (LINE Messaging API has no outbound file type)
		text = (
			self._to_https(message["file_url"]) if msg_type == "File" else message.get("text", "")
		)
		line_msg = LineTextMessage(text=text)
		if sender:
			line_msg.sender = sender
		return line_msg

	def send_reply(self, user_id: str, message: dict, context: Any) -> None:
		reply_token = (context or {}).get("reply_token")
		line_msg = self._build_outbound_message(message)
		if reply_token:
			try:
				with ApiClient(self.config) as api_client:
					MessagingApi(api_client).reply_message(
						ReplyMessageRequest(reply_token=reply_token, messages=[line_msg])
					)
				return
			except Exception:
				pass
		with ApiClient(self.config) as api_client:
			MessagingApi(api_client).push_message(
				PushMessageRequest(to=user_id, messages=[line_msg])
			)

	def send_message(self, user_id: str, message: dict) -> None:
		with ApiClient(self.config) as api_client:
			MessagingApi(api_client).push_message(
				PushMessageRequest(to=user_id, messages=[self._build_outbound_message(message)])
			)

	def _download_line_content(self, message_id: str) -> bytes:
		with ApiClient(self.config) as api_client:
			return bytes(MessagingApiBlob(api_client).get_message_content(message_id))

	def event_mapper(self, event: LineEvent) -> dict | None:
		if not isinstance(event, LineMessageEvent):
			return None

		msg = event.message
		metadata = {"message_id": msg.id, "reply_token": event.reply_token}

		if isinstance(msg, TextMessageContent):
			return {
				"provider": self.provider_config.provider,
				"user_id": event.source.user_id,
				"message": {"type": "Text", "text": msg.text},
				"message_metadata": metadata,
			}

		if isinstance(msg, ImageMessageContent):
			return {
				"provider": self.provider_config.provider,
				"user_id": event.source.user_id,
				"message": {
					"type": "Image",
					"file_name": f"{msg.id}.jpg",
					"file_content": self._download_line_content(msg.id),
				},
				"message_metadata": metadata,
			}

		if isinstance(msg, FileMessageContent):
			return {
				"provider": self.provider_config.provider,
				"user_id": event.source.user_id,
				"message": {
					"type": "File",
					"file_name": msg.file_name,
					"file_content": self._download_line_content(msg.id),
				},
				"message_metadata": metadata,
			}

		return None

	def standardize_events(self, events: list[LineEvent]) -> list[dict]:
		std_events: list[dict] = []
		for event in events:
			std_event = self.event_mapper(event)
			if std_event:
				std_events.append(std_event)
		return std_events

	def extract_messages(self, body: bytes, headers: dict) -> list[dict]:
		signature = headers.get("x-line-signature", "") or headers.get("X-Line-Signature", "")
		try:
			events = self.parser.parse(body=body.decode(), signature=signature, as_payload=False)
		except InvalidSignatureError:
			frappe.throw("Invalid LINE signature", frappe.PermissionError)
		return self.standardize_events(events)
