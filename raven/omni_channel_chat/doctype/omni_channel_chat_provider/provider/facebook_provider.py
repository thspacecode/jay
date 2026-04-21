import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any, Callable

import frappe
import httpx
from werkzeug.wrappers import Response

from raven.omni_channel_chat.doctype.omni_channel_chat_provider.provider import (
	Provider,
)
from raven.omni_channel_chat.models.message import (
	BaseMessage,
	FileContent,
	FileMessage,
	ImageMessage,
	TextMessage,
	UserInfo,
)

# A "messaging event" dict from the Facebook webhook payload
FacebookMessagingEvent = dict[str, Any]


@dataclass
class FacebookConfig:
	app_secret: str
	page_access_token: str
	verify_token: str


class FacebookProvider(Provider[FacebookMessagingEvent]):
	fb_api_url = "https://graph.facebook.com/v25.0"

	def __init__(self, config):
		super().__init__(config=config)
		self.config = FacebookConfig(
			app_secret=self.provider_config.fb_app_secret,
			page_access_token=self.provider_config.fb_page_access_token,
			verify_token=self.provider_config.fb_verify_token,
		)

	def verify_token(self) -> Response:
		mode = frappe.form_dict.get("hub.mode")
		verify_token = frappe.form_dict.get("hub.verify_token")
		challenge = frappe.form_dict.get("hub.challenge", "0")

		if mode == "subscribe" and verify_token == self.config.verify_token:
			return Response(challenge, status=200, content_type="text/plain")
		else:
			frappe.throw("Verification failed", frappe.PermissionError)

	def handle_frappe_api(self, callback: Callable[[BaseMessage], None]) -> Response:
		request = frappe.local.request

		if request.method == "GET":
			return self.verify_token()
		elif request.method == "POST":
			body: bytes = request.get_data()
			headers: dict = dict(request.headers)
			return self.handle_webhook(body=body, headers=headers, callback=callback)
		else:
			return Response("Method Not Allowed", status=405, content_type="text/plain")

	def verify_signature(self, body: bytes, signature_header: str) -> bool:
		if not signature_header.startswith("sha256="):
			return False
		expected = hmac.new(self.config.app_secret.encode(), body, hashlib.sha256).hexdigest()
		return hmac.compare_digest(expected, signature_header.removeprefix("sha256="))

	def get_user_info(self, user_id: str) -> UserInfo:
		with httpx.Client() as client:
			response = client.get(
				f"{self.fb_api_url}/{user_id}",
				params={
					"fields": "name,picture",
					"access_token": self.config.page_access_token,
				},
			)
			response.raise_for_status()
			data = response.json()
			return UserInfo(
				user_id=user_id,
				display_name=data.get("name"),
				picture_url=data.get("picture", {}).get("data", {}).get("url"),
			)

	def show_typing(self, user_id: str) -> None:
		with httpx.Client() as client:
			client.post(
				f"{self.fb_api_url}/me/messages",
				params={"access_token": self.config.page_access_token},
				json={"recipient": {"id": user_id}, "sender_action": "typing_on"},
			)

	def send_reply(self, message: BaseMessage) -> None:
		self.send_message(message)

	def send_message(self, message: BaseMessage) -> None:
		with httpx.Client() as client:
			client.post(
				f"{self.fb_api_url}/me/messages",
				params={"access_token": self.config.page_access_token},
				json={"recipient": {"id": message.user_id}, "message": message.to_provider()},
			)

	def download_attachment(self, url: str, file_name: str | None = None) -> FileContent:
		with httpx.Client() as client:
			response = client.get(url)
			response.raise_for_status()
			content_disposition = response.headers.get("content-disposition", "")
			file_name = file_name or "attachment"
			if "filename=" in content_disposition:
				file_name = content_disposition.split("filename=")[-1].strip('" ')
			return FileContent(file_name=file_name, file_content=response.content)

	def event_mapper(self, event: FacebookMessagingEvent) -> BaseMessage | None:
		message = event.get("message")
		if message is None:
			return None

		mid = message.get("mid")
		user_id = event["sender"]["id"]
		metadata = {"mid": mid}

		if "text" in message:
			return TextMessage(
				provider=self.provider_config.provider,
				provider_id=self.provider_config.name,
				user_id=user_id,
				metadata=metadata,
				text=message["text"],
			)

		for attachment in message.get("attachments") or []:
			att_type = attachment.get("type")
			url = attachment.get("payload", {}).get("url")
			if not url:
				continue
			if att_type == "image":
				return ImageMessage(
					provider=self.provider_config.provider,
					provider_id=self.provider_config.name,
					user_id=user_id,
					metadata=metadata,
					file=self.download_attachment(url),
				)
			if att_type in ("file", "document"):
				return FileMessage(
					provider=self.provider_config.provider,
					provider_id=self.provider_config.name,
					user_id=user_id,
					metadata=metadata,
					file=self.download_attachment(url),
				)

		return None

	def standardize_events(self, events: list[FacebookMessagingEvent]) -> list[BaseMessage]:
		std_events: list[BaseMessage] = []
		for event in events:
			std_event = self.event_mapper(event)
			if std_event:
				std_events.append(std_event)
		return std_events

	def extract_messages(self, body: bytes, headers: dict) -> list[BaseMessage]:
		signature = headers.get("X-Hub-Signature-256", "") or headers.get(
			"x-hub-signature-256", ""
		)
		if not self.verify_signature(body, signature):
			frappe.throw("Invalid Facebook signature", frappe.PermissionError)

		payload = json.loads(body)
		if payload.get("object") != "page":
			frappe.throw("Not a page event", frappe.ValidationError)

		messaging_events: list[FacebookMessagingEvent] = [
			messaging_event
			for entry in payload.get("entry", [])
			for messaging_event in entry.get("messaging", [])
		]
		return self.standardize_events(messaging_events)
