import hashlib
import hmac
import json
from typing import Any

import frappe
import httpx

from raven.omni_channel_chat.doctype.omni_channel_chat_provider.provider import (
	Provider,
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

	def _verify_signature(self, body: bytes, signature_header: str) -> bool:
		if not signature_header.startswith("sha256="):
			return False
		expected = hmac.new(self._app_secret.encode(), body, hashlib.sha256).hexdigest()
		return hmac.compare_digest(expected, signature_header.removeprefix("sha256="))

	async def get_user_info(self, user_id: str) -> dict:
		async with httpx.AsyncClient() as client:
			response = await client.get(
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

	async def show_typing(self, user_id: str) -> None:
		async with httpx.AsyncClient() as client:
			await client.post(
				self.FB_API_URL,
				params={"access_token": self._page_access_token},
				json={"recipient": {"id": user_id}, "sender_action": "typing_on"},
			)

	async def send_reply(self, user_id: str, message: dict, context: Any) -> None:
		await self.send_message(user_id=user_id, message=message)

	async def send_message(self, user_id: str, message: dict) -> None:
		async with httpx.AsyncClient() as client:
			await client.post(
				self.FB_API_URL,
				params={"access_token": self._page_access_token},
				json={
					"recipient": {"id": user_id},
					"message": {"text": message["text"]},
				},
			)

	async def event_mapper(self, event: FacebookMessagingEvent) -> dict | None:
		message = event.get("message")
		if message is None or "text" not in message:
			return None
		return {
			"provider": self.provider_config.provider,
			"user_id": event["sender"]["id"],
			"message": {"type": "Text", "text": message["text"]},
			"message_metadata": {"mid": message.get("mid")},
		}

	async def standardize_events(self, events: list[FacebookMessagingEvent]) -> list[dict]:
		std_events: list[dict] = []
		for event in events:
			std_event = await self.event_mapper(event)
			if std_event:
				std_events.append(std_event)
		return std_events

	async def extract_messages(self, body: bytes, headers: dict) -> list[dict]:
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
		return await self.standardize_events(messaging_events)
