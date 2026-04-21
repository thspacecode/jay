from typing import Callable

import frappe
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
	ApiClient,
	Configuration,
	MessagingApi,
	MessagingApiBlob,
	PushMessageRequest,
	ReplyMessageRequest,
	ShowLoadingAnimationRequest,
)
from linebot.v3.webhook import WebhookParser
from linebot.v3.webhooks import Event as LineEvent
from linebot.v3.webhooks import FileMessageContent, ImageMessageContent, TextMessageContent
from linebot.v3.webhooks import MessageEvent as LineMessageEvent
from werkzeug.wrappers import Response

from raven.omni_channel_chat.models.message import (
	BaseMessage,
	FileContent,
	FileMessage,
	ImageMessage,
)
from raven.omni_channel_chat.models.message import (
	TextMessage as StdTextMessage,
)

from . import Provider


class LineProvider(Provider[LineEvent]):
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

	def handle_frappe_api(self, callback: Callable[[BaseMessage], None]) -> Response:
		request = frappe.local.request
		body: bytes = request.get_data()
		headers: dict = dict(request.headers)
		return self.handle_webhook(body=body, headers=headers, callback=callback)

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

	def send_reply(self, message: BaseMessage) -> None:
		reply_token = (message.metadata or {}).get("reply_token")
		line_msg = message.to_provider()
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
				PushMessageRequest(to=message.user_id, messages=[line_msg])
			)

	def send_message(self, message: BaseMessage) -> None:
		with ApiClient(self.config) as api_client:
			MessagingApi(api_client).push_message(
				PushMessageRequest(to=message.user_id, messages=[message.to_provider()])
			)

	def download_attachment(self, message_id: str, file_name: str | None = None) -> FileContent:
		with ApiClient(self.config) as api_client:
			content = bytes(MessagingApiBlob(api_client).get_message_content(message_id))
			return FileContent(file_name=file_name or "attachment", file_content=content)

	def event_mapper(self, event: LineEvent) -> BaseMessage | None:
		if not isinstance(event, LineMessageEvent):
			return None

		msg = event.message
		metadata = {"message_id": msg.id, "reply_token": event.reply_token}
		user_id = event.source.user_id

		if isinstance(msg, TextMessageContent):
			return StdTextMessage(
				provider="line", user_id=user_id, metadata=metadata, text=msg.text
			)

		if isinstance(msg, ImageMessageContent):
			return ImageMessage(
				provider="line",
				user_id=user_id,
				metadata=metadata,
				file=self.download_attachment(msg.id, f"{msg.id}.jpg"),
			)

		if isinstance(msg, FileMessageContent):
			return FileMessage(
				provider="line",
				user_id=user_id,
				metadata=metadata,
				file=self.download_attachment(msg.id, msg.file_name),
			)

		return None

	def standardize_events(self, events: list[LineEvent]) -> list[BaseMessage]:
		std_events: list[BaseMessage] = []
		for event in events:
			std_event = self.event_mapper(event)
			if std_event:
				std_events.append(std_event)
		return std_events

	def extract_messages(self, body: bytes, headers: dict) -> list[BaseMessage]:
		signature = headers.get("x-line-signature", "") or headers.get("X-Line-Signature", "")
		try:
			events = self.parser.parse(body=body.decode(), signature=signature, as_payload=False)
		except InvalidSignatureError:
			frappe.throw("Invalid LINE signature", frappe.PermissionError)
		return self.standardize_events(events)
