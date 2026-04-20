from typing import Any

import frappe
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
	ApiClient,
	Configuration,
	MessagingApi,
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
from linebot.v3.webhooks import MessageEvent as LineMessageEvent
from linebot.v3.webhooks import TextMessageContent

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

	def send_reply(self, user_id: str, message: dict, context: Any) -> None:
		reply_token = (context or {}).get("reply_token")
		line_msg = LineTextMessage(text=message["text"])
		if message.get("sender"):
			line_msg.sender = LineSender(
				name=message["sender"].get("name"),
				icon_url=message["sender"].get("icon_url"),
			)
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
		line_msg = LineTextMessage(text=message["text"])
		if message.get("sender"):
			line_msg.sender = LineSender(
				name=message["sender"].get("name"),
				icon_url=message["sender"].get("icon_url"),
			)
		with ApiClient(self.config) as api_client:
			MessagingApi(api_client).push_message(
				PushMessageRequest(
					to=user_id,
					messages=[line_msg],
				)
			)

	def event_mapper(self, event: LineEvent) -> dict | None:
		if not isinstance(event, LineMessageEvent):
			return None

		msg = event.message
		if isinstance(msg, TextMessageContent):
			return {
				"provider": self.provider_config.provider,
				"user_id": event.source.user_id,
				"message": {"type": "Text", "text": msg.text},
				"message_metadata": {
					"message_id": msg.id,
					"reply_token": event.reply_token,
				},
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
