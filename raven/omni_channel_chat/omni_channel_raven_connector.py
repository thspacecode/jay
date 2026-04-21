from typing import TYPE_CHECKING, cast

import frappe
from frappe.utils import get_url

from raven.omni_channel_chat.models.message import (
	BaseMessage,
	FileContent,
	FileMessage,
	FileUrl,
	ImageMessage,
	SenderInfo,
	TextMessage,
)

if TYPE_CHECKING:
	from frappe.core.doctype.user.user import User

	from raven.omni_channel_chat.doctype.omni_channel_chat_provider.omni_channel_chat_provider import (
		OmniChannelChatProvider,
	)
	from raven.omni_channel_chat.doctype.omni_channel_chat_provider.provider import (
		Provider,
	)
	from raven.raven.doctype.raven_user.raven_user import RavenUser
	from raven.raven_channel_management.doctype.raven_channel.raven_channel import (
		RavenChannel,
	)
	from raven.raven_messaging.doctype.raven_message.raven_message import RavenMessage


def _resolve_sender(owner: str) -> "SenderInfo | None":
	raven_user = cast(
		"dict | None",
		frappe.db.get_value("Raven User", owner, ["full_name", "user_image"], as_dict=True),
	)
	if not raven_user:
		return None
	avatar_url = cast("str | None", raven_user["user_image"])
	if avatar_url and avatar_url.startswith("/"):
		avatar_url = get_url(avatar_url)
	return SenderInfo(name=raven_user["full_name"] or "", icon_url=avatar_url or None)


def _build_outbound_message(
	raven_message: "RavenMessage", sender: "SenderInfo | None", provider_name: str
) -> BaseMessage:
	msg_type = raven_message.message_type
	if msg_type == "Text":
		return TextMessage(
			provider=provider_name, user_id="", text=raven_message.content or "", sender=sender
		)
	file_url = raven_message.file
	if file_url and file_url.startswith("/"):
		file_url = get_url(file_url)
	if msg_type == "Image":
		return ImageMessage(
			provider=provider_name, user_id="", file=FileUrl(url=file_url or ""), sender=sender
		)
	if msg_type == "File":
		return FileMessage(
			provider=provider_name, user_id="", file=FileUrl(url=file_url or ""), sender=sender
		)
	raise ValueError(f"Unsupported outbound message type: {msg_type}")


class OmniChannelRavenConnector:
	"""Bridges Raven and an external omni-channel provider.

	Two main interfaces:
	    receive_from_provider – inbound path: provider webhook payload → Raven message
	    push_to_provider      – outbound path: Raven message → external provider
	"""

	def __init__(self, provider: "Provider"):
		self.provider = provider
		self.chat_integration: "OmniChannelChatProvider" = provider.provider_config

	# ── shared helpers ──────────────────────────────────────────────────────

	def _get_or_create_customer_user(self, user_id: str) -> "User":
		provider_name = self.chat_integration.provider

		user_pk = frappe.db.get_value(
			doctype="User Social Login",
			filters={"provider": provider_name, "userid": user_id},
			fieldname="parent",
		)

		if user_pk:
			return cast("User", frappe.get_doc("User", str(user_pk)))

		username = frappe.generate_hash(length=10)
		email = f"{username}@users.cafn.co"

		user = frappe.new_doc("User")
		user.update(
			{
				"email": email,
				"username": username,
				"first_name": username,
				"enabled": 1,
				"user_type": "Website User",
			}
		)
		user.insert(ignore_permissions=True)

		user_social_login = frappe.new_doc("User Social Login")
		user_social_login.update(
			{
				"provider": provider_name,
				"userid": user_id,
				"parent": user.name,
				"parenttype": "User",
				"parentfield": "social_logins",
			}
		)
		user_social_login.insert(ignore_permissions=True)

		return cast("User", user)

	def _get_or_create_raven_user(self, *, user: "User", user_id: str) -> "RavenUser":
		raven_user_pk = frappe.db.get_value(
			doctype="Raven User",
			filters={"user": user.name},
			fieldname="name",
		)

		if raven_user_pk:
			return cast("RavenUser", frappe.get_doc("Raven User", str(raven_user_pk)))

		user_info = self.provider.get_user_info(user_id=user_id)
		raven_user = frappe.new_doc("Raven User")
		raven_user.update(
			{
				"type": "Customer",
				"user": user.name,
				"full_name": user_info["display_name"],
				"user_image": user_info["picture_url"],
				"enabled": True,
			}
		)
		raven_user.insert(ignore_permissions=True)

		return cast("RavenUser", raven_user)

	def _get_or_create_channel(self, raven_user: "RavenUser") -> "RavenChannel":
		channel_name = f"{self.chat_integration.name}_{raven_user.name}"
		channel_pk = frappe.db.get_value(
			doctype="Raven Channel",
			filters=channel_name,
			fieldname="name",
		)

		if channel_pk:
			return cast("RavenChannel", frappe.get_doc("Raven Channel", str(channel_pk)))

		return cast(
			"RavenChannel",
			frappe.get_doc(
				{
					"doctype": "Raven Channel",
					"channel_name": channel_name,
					"id": channel_name,
					"type": "Public",
					"customer_user": raven_user.user,
					"omni_channel_chat_provider": self.chat_integration.name,
					"is_customer": True,
					"enabled": True,
					"workspace": self.chat_integration.raven_workspace,
				}
			).insert(ignore_permissions=True),
		)

	def _get_external_user_id(self, customer_user: str) -> str:
		"""Resolve the provider's external user_id for a given Frappe user."""
		user_id = frappe.db.get_value(
			doctype="User Social Login",
			filters={
				"provider": self.chat_integration.provider,
				"parent": customer_user,
			},
			fieldname="userid",
		)
		if not user_id:
			frappe.throw(
				f"No {self.chat_integration.provider} social login found for user {customer_user}"
			)
		return cast(str, user_id)

	# ── interface 1: provider → Raven (inbound) ─────────────────────────────

	def handle_webhook(self, body: bytes, headers: dict) -> None:
		"""Parse a raw webhook payload and persist all contained messages to Raven."""
		messages = self.provider.extract_messages(body=body, headers=headers)
		for message in messages:
			self.receive_from_provider(message)

	def receive_from_provider(self, message: BaseMessage) -> None:
		"""Inbound: turn a provider webhook payload into a Raven message.

		Creates the Frappe user, Raven user, and channel on first contact,
		then appends the message to the channel.

		Returns the Raven channel the message was posted to.
		"""
		user = self._get_or_create_customer_user(user_id=message.user_id or "")
		frappe.set_user(str(user.name))

		raven_user = self._get_or_create_raven_user(user=user, user_id=message.user_id)
		raven_channel = self._get_or_create_channel(raven_user=raven_user)
		self._save_inbound_message(raven_channel=raven_channel, message=message)

	def _save_inbound_message(
		self, *, raven_channel: "RavenChannel", message: BaseMessage
	) -> None:
		doc = frappe.new_doc(doctype="Raven Message")
		doc.update(
			{
				"channel_id": raven_channel.name,
				"message_type": message.type,
				"is_customer_message": True,
				"owner": raven_channel.customer_user,
				"omni_channel_msg_meta": message.metadata,
			}
		)
		if isinstance(message, TextMessage):
			doc.text = message.text
		elif isinstance(message, (ImageMessage, FileMessage)) and isinstance(
			message.file, FileContent
		):
			file_doc = frappe.get_doc(
				{
					"doctype": "File",
					"file_name": message.file.file_name,
					"content": message.file.file_content,
					"is_private": 0,
				}
			)
			file_doc.insert(ignore_permissions=True)
			doc.file = file_doc.file_url
		doc.insert(ignore_permissions=True)

	# ── interface 2: Raven → provider (outbound) ────────────────────────────

	@classmethod
	def push_to_provider(cls, raven_message: "RavenMessage") -> None:
		"""Outbound: forward a staff Raven message to the customer on the external provider.

		Handles guard conditions, channel/provider resolution, message payload building
		(text + sender avatar), reply-context fetch (e.g. LINE reply token), and dispatch.
		Does nothing if the message is from a customer, a bot, or is a system message,
		or if the channel is not an omni-channel customer channel.
		"""
		if (
			raven_message.is_customer_message
			or raven_message.is_bot_message
			or raven_message.message_type in ("System", "Poll")
		):
			return

		channel = cast(
			"dict | None",
			frappe.db.get_value(
				doctype="Raven Channel",
				filters=raven_message.channel_id,
				fieldname=["is_customer", "customer_user", "omni_channel_chat_provider"],
				as_dict=True,
				cache=True,
			),
		)

		if not channel or not channel["is_customer"] or not channel["omni_channel_chat_provider"]:
			return

		provider_config = frappe.get_doc(
			"Omni Channel Chat Provider", channel["omni_channel_chat_provider"]
		)
		connector = cls(provider=provider_config.get_provider())

		user_id = frappe.db.get_value(
			doctype="User Social Login",
			filters={
				"provider": connector.chat_integration.provider,
				"parent": channel["customer_user"],
			},
			fieldname="userid",
		)
		if not user_id:
			return

		provider_name = connector.chat_integration.provider
		sender = _resolve_sender(raven_message.owner)
		outbound_msg = _build_outbound_message(raven_message, sender, provider_name)
		outbound_msg.user_id = str(user_id)
		outbound_msg.metadata = frappe.parse_json(
			cast(
				str,
				frappe.db.get_value(
					"Raven Message",
					filters={"channel_id": raven_message.channel_id, "is_customer_message": 1},
					fieldname="omni_channel_msg_meta",
					order_by="creation desc",
				),
			)
		)

		connector.provider.send_reply(message=outbound_msg)

	@classmethod
	def send_outbound_message(
		cls, channel_name: str, message: BaseMessage, owner: str | None = None
	) -> None:
		"""Push a typed outbound message to the external provider for a given Raven channel.

		Unlike push_to_provider (which is triggered by a Raven message doc), this method
		accepts any BaseMessage directly — e.g. TrackingStatusMessage — and dispatches
		it to the provider without creating a Raven message first.
		"""
		channel = cast(
			"dict | None",
			frappe.db.get_value(
				doctype="Raven Channel",
				filters=channel_name,
				fieldname=["is_customer", "customer_user", "omni_channel_chat_provider"],
				as_dict=True,
			),
		)
		if not channel or not channel["is_customer"] or not channel["omni_channel_chat_provider"]:
			return

		provider_config = frappe.get_doc(
			"Omni Channel Chat Provider", channel["omni_channel_chat_provider"]
		)
		connector = cls(provider=provider_config.get_provider())

		user_id = frappe.db.get_value(
			doctype="User Social Login",
			filters={
				"provider": connector.chat_integration.provider,
				"parent": channel["customer_user"],
			},
			fieldname="userid",
		)
		if not user_id:
			return

		if message.sender is None and owner:
			message.sender = _resolve_sender(owner)

		message.user_id = str(user_id)
		connector.provider.send_message(message=message)
