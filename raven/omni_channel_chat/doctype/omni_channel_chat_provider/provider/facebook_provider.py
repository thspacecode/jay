import hashlib
import hmac
import json
from typing import Any

import frappe
import httpx
from werkzeug.wrappers import Response

from raven.omni_channel_chat.doctype.omni_channel_chat_provider.provider import (
	Provider,
)
from raven.omni_channel_chat.models.messages import (
	FileMessage,
	ImageMessage,
	StdMessage,
	TextMessage,
)

# A "messaging event" dict from the Facebook webhook payload
FacebookMessagingEvent = dict[str, Any]


class FacebookProvider(Provider[FacebookMessagingEvent, dict]):
	FB_API_URL = "https://graph.facebook.com/v22.0/me/messages"

	def __init__(self, config):
		super().__init__(config=config)
		self._page_access_token = self.provider_config.fb_page_access_token
		self._app_secret = self.provider_config.fb_app_secret
		self._verify_token = self.provider_config.fb_verify_token

	def handle_frappe_api(self):
		request = frappe.local.request

		if request.method == "GET":
			mode = frappe.form_dict.get("hub.mode")
			verify_token = frappe.form_dict.get("hub.verify_token")
			challenge = frappe.form_dict.get("hub.challenge", "0")

			if mode == "subscribe" and verify_token == self._verify_token:
				return Response(challenge, status=200, content_type="text/plain")
			else:
				frappe.throw("Verification failed", frappe.PermissionError)

		body: bytes = request.get_data()
		headers: dict = dict(request.headers)

		return self.handle_webhook(body=body, headers=headers)

	def _verify_signature(self, body: bytes, signature_header: str) -> bool:
		if not signature_header.startswith("sha256="):
			return False
		expected = hmac.new(self._app_secret.encode(), body, hashlib.sha256).hexdigest()
		return hmac.compare_digest(expected, signature_header.removeprefix("sha256="))

	def get_user_info(self, user_id: str) -> dict:
		with httpx.Client() as client:
			response = client.get(
				f"https://graph.facebook.com/{user_id}",
				params={
					"fields": "name,picture",
					"access_token": self._page_access_token,
				},
			)
			response.raise_for_status()
			data = response.json()
			return {
				"user_id": user_id,
				"display_name": data.get("name"),
				"picture_url": data.get("picture", {}).get("data", {}).get("url"),
			}

	def show_typing(self, user_id: str) -> None:
		with httpx.Client() as client:
			client.post(
				self.FB_API_URL,
				params={"access_token": self._page_access_token},
				json={"recipient": {"id": user_id}, "sender_action": "typing_on"},
			)

	def send_reply(self, user_id: str, message: dict, context: Any) -> None:
		self.send_message(user_id=user_id, message=message)

	def send_message(self, user_id: str, message: dict) -> None:
		msg_type = message.get("type", "Text")
		if msg_type == "Image":
			fb_message = {
				"attachment": {
					"type": "image",
					"payload": {"url": message["file_url"], "is_reusable": True},
				}
			}
		elif msg_type == "File":
			fb_message = {
				"attachment": {
					"type": "file",
					"payload": {"url": message["file_url"], "is_reusable": True},
				}
			}
		else:
			fb_message = {"text": message["text"]}
		with httpx.Client() as client:
			client.post(
				self.FB_API_URL,
				params={"access_token": self._page_access_token},
				json={"recipient": {"id": user_id}, "message": fb_message},
			)

	def _download_attachment(self, url: str, default_name: str) -> tuple[bytes, str]:
		with httpx.Client() as client:
			response = client.get(url)
			response.raise_for_status()
			content_disposition = response.headers.get("content-disposition", "")
			file_name = default_name
			if "filename=" in content_disposition:
				file_name = content_disposition.split("filename=")[-1].strip('" ')
			return response.content, file_name

	def event_mapper(self, event: FacebookMessagingEvent) -> StdMessage | None:
		message = event.get("message")
		if message is None:
			return None

		mid = message.get("mid")
		user_id = event["sender"]["id"]
		metadata = {"mid": mid}

		if "text" in message:
			return TextMessage(user_id=user_id, metadata=metadata, text=message["text"])

		for attachment in message.get("attachments") or []:
			att_type = attachment.get("type")
			url = attachment.get("payload", {}).get("url")
			if not url:
				continue
			if att_type == "image":
				content, file_name = self._download_attachment(url, f"{mid or 'image'}.jpg")
				return ImageMessage(
					user_id=user_id, metadata=metadata, file_name=file_name, file_content=content
				)
			if att_type in ("file", "document"):
				content, file_name = self._download_attachment(url, mid or "file")
				return FileMessage(
					user_id=user_id, metadata=metadata, file_name=file_name, file_content=content
				)

		return None

	def standardize_events(self, events: list[FacebookMessagingEvent]) -> list[StdMessage]:
		std_events: list[StdMessage] = []
		for event in events:
			std_event = self.event_mapper(event)
			if std_event:
				std_events.append(std_event)
		return std_events

	def extract_messages(self, body: bytes, headers: dict) -> list[StdMessage]:
		signature = headers.get("X-Hub-Signature-256", "") or headers.get(
			"x-hub-signature-256", ""
		)
		if not self._verify_signature(body, signature):
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
