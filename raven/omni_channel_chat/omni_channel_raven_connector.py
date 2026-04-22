from typing import TYPE_CHECKING, cast

import frappe
from frappe import _
from frappe.utils import get_host_name, get_site_name, get_url

from raven.omni_channel_chat.doctype.omni_channel_chat_provider.omni_channel_chat_provider import (
	get_omni_channel_chat_provider,
)
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

	from raven.omni_channel_chat.doctype.omni_channel_chat_provider.provider import (
		Provider,
	)
	from raven.raven.doctype.raven_user.raven_user import RavenUser
	from raven.raven_channel_management.doctype.raven_channel.raven_channel import (
		RavenChannel,
	)
	from raven.raven_messaging.doctype.raven_message.raven_message import RavenMessage


class OmniChannelRavenConnector:
	provider_prefix = "occ"

	def __init__(self, provider: "Provider"):
		self.provider = provider

	@staticmethod
	def get_provider_from_channel(channel_name: str) -> "Provider":
		provider_name = frappe.db.get_value(
			doctype="Raven Channel",
			filters=channel_name,
			fieldname="omni_channel_chat_provider",
		)
		if not provider_name:
			frappe.throw(
				_("Omni Channel Chat Provider not found for channel {0}").format(channel_name)
			)
		return get_omni_channel_chat_provider(
			slug=provider_name,
		)

	def get_provider_pk(self, provider_id: str) -> str:
		return f"{self.provider_prefix}_{provider_id}"

	def get_channel_name(self, raven_user: "RavenUser") -> str:
		return f"{self.provider.provider_config.name}_{raven_user.name}"

	def get_sender_info(self, owner: str) -> "SenderInfo | None":
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

	def get_user_id(self, channel_id: str) -> str:
		channel_user = frappe.db.get_value(
			doctype="Raven Channel",
			filters=channel_id,
			fieldname="customer_user",
		)

		user_id = frappe.db.get_value(
			doctype="User Social Login",
			filters={
				"provider": self.get_provider_pk(self.provider.provider_config.name),
				"parent": channel_user,
			},
			fieldname="userid",
		)

		if not user_id:
			frappe.throw(_("User ID not found for channel {0}").format(channel_id))

		return user_id

	def raven_to_std_msg(
		self,
		raven_message: "RavenMessage",
		user_id: str,
		sender: "SenderInfo | None",
	) -> BaseMessage:
		provider_id = self.provider.provider_config.name
		msg_type = raven_message.message_type
		if msg_type == "Text":
			return TextMessage(
				provider=self.provider.provider_config.provider,
				provider_id=provider_id,
				user_id=user_id,
				text=raven_message.content or "",
				sender=sender,
			)
		file_url = raven_message.file
		if file_url and file_url.startswith("/"):
			file_url = get_url(file_url)
		if msg_type == "Image":
			return ImageMessage(
				provider=self.provider.provider_config.provider,
				provider_id=provider_id,
				user_id=user_id,
				file=FileUrl(url=file_url or ""),
				sender=sender,
			)
		if msg_type == "File":
			return FileMessage(
				provider=self.provider.provider_config.provider,
				provider_id=provider_id,
				user_id=user_id,
				file=FileUrl(url=file_url or ""),
				sender=sender,
			)

		raise ValueError(f"Unsupported outbound message type: {msg_type}")

	def get_hostname_without_port(self) -> str:
		return get_site_name(get_host_name())

	def create_customer_user(self, user_id: str, provider_id: str) -> "User":
		provider_pk = self.get_provider_pk(provider_id)

		username = frappe.generate_hash(length=10)
		hostname = self.get_hostname_without_port()

		email = f"{username}@{self.provider_prefix}.{hostname}"

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
				"provider": provider_pk,
				"userid": user_id,
				"parent": user.name,
				"parenttype": "User",
				"parentfield": "social_logins",
			}
		)
		user_social_login.insert(ignore_permissions=True)

		return user

	def get_or_create_customer_user(self, user_id: str | None, provider_id: str) -> "User":
		provider_pk = self.get_provider_pk(provider_id)

		user_pk = frappe.db.get_value(
			doctype="User Social Login",
			filters={"provider": provider_pk, "userid": user_id},
			fieldname="parent",
		)

		if user_pk:
			return frappe.get_doc("User", user_pk)

		return self.create_customer_user(user_id=user_id, provider_id=provider_id)

	def create_raven_user(self, user: "User", user_id: str) -> "RavenUser":
		user_info = self.provider.get_user_info(user_id=user_id)

		raven_user = frappe.new_doc("Raven User")
		raven_user.update(
			{
				"type": "Customer",
				"user": user.name,
				"full_name": user_info.display_name,
				"user_image": user_info.picture_url,
				"enabled": True,
			}
		)
		raven_user.insert(ignore_permissions=True)

		return raven_user

	def get_or_create_raven_user(self, user: "User", user_id: str) -> "RavenUser":
		raven_user_pk = frappe.db.get_value(
			doctype="Raven User",
			filters={"user": user.name},
			fieldname="name",
		)

		if raven_user_pk:
			return frappe.get_doc("Raven User", raven_user_pk)

		return self.create_raven_user(user=user, user_id=user_id)

	def create_channel(self, raven_user: "RavenUser") -> "RavenChannel":
		channel_name = self.get_channel_name(raven_user)

		channel = frappe.new_doc("Raven Channel")
		channel.update(
			{
				"channel_name": channel_name,
				"id": channel_name,
				"type": "Public",
				"customer_user": raven_user.user,
				"omni_channel_chat_provider": self.provider.provider_config.name,
				"is_customer": True,
				"enabled": True,
				"workspace": self.provider.provider_config.raven_workspace,
			}
		)
		channel.insert(ignore_permissions=True)

		return channel

	def get_or_create_channel(self, raven_user: "RavenUser") -> "RavenChannel":
		channel_name = self.get_channel_name(raven_user)

		channel_pk = frappe.db.get_value(
			doctype="Raven Channel",
			filters=channel_name,
			fieldname="name",
		)

		if channel_pk:
			return frappe.get_doc("Raven Channel", channel_pk)

		return self.create_channel(raven_user)

	def create_raven_message(self, raven_channel: "RavenChannel", message: BaseMessage) -> None:
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

	# ── provider → Raven (inbound) ─────────────────────────────

	def handle_inbound(self, message: BaseMessage) -> None:
		"""Inbound: turn a provider webhook payload into a Raven message.

		Creates the Frappe user, Raven user, and channel on first contact,
		then appends the message to the channel.

		Returns the Raven channel the message was posted to.
		"""
		user_id = message.user_id

		user = self.get_or_create_customer_user(
			user_id=user_id,
			provider_id=message.provider_id,
		)

		frappe.set_user(user.name)

		raven_user = self.get_or_create_raven_user(
			user=user,
			user_id=user_id,
		)
		raven_channel = self.get_or_create_channel(
			raven_user=raven_user,
		)
		self.create_raven_message(
			raven_channel=raven_channel,
			message=message,
		)

	# ── Raven → provider (outbound) ────────────────────────────

	def handle_outbound(self, raven_message: "RavenMessage") -> None:
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

		user_id = self.get_user_id(channel_id=raven_message.channel_id)
		sender = self.get_sender_info(owner=raven_message.owner)
		outbound_msg = self.raven_to_std_msg(
			raven_message=raven_message,
			sender=sender,
			user_id=user_id,
		)
		self.provider.send_reply(message=outbound_msg)
