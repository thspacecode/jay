from typing import TYPE_CHECKING

import frappe

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


class WebhookMessageHandler:
	def __init__(self, provider: "Provider"):
		self.provider = provider
		self.chat_integration: "OmniChannelChatProvider" = provider.provider_config

	def get_customer_user(self, user_id: str) -> "User":
		provider_name = self.chat_integration.provider

		user_pk = frappe.db.get_value(
			doctype="User Social Login",
			filters={
				"provider": provider_name,
				"userid": user_id,
			},
			fieldname="parent",
		)

		if user_pk:
			user = frappe.get_doc("User", user_pk)
		else:
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

		return user

	def get_raven_user(self, *, user: "User", user_id: str) -> "RavenUser":
		raven_user_pk = frappe.db.get_value(
			doctype="Raven User",
			filters={
				"user": user.name,
			},
			fieldname="name",
		)

		if raven_user_pk:
			raven_user = frappe.get_doc("Raven User", raven_user_pk)
		else:
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

		return raven_user

	def get_raven_channel(self, raven_user: "RavenUser") -> "RavenChannel":
		channel_name = f"{self.chat_integration.name}_{raven_user.name}"
		channel_pk = frappe.db.get_value(
			doctype="Raven Channel",
			filters=channel_name,
			fieldname="name",
		)

		if channel_pk:
			channel = frappe.get_doc("Raven Channel", channel_pk)
		else:
			channel = frappe.get_doc(
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
			).insert(ignore_permissions=True)

		return channel

	def create_message(self, *, raven_channel: "RavenChannel", message: dict) -> None:
		doc = frappe.new_doc(doctype="Raven Message")
		doc.update(
			{
				"channel_id": raven_channel.name,
				"message_type": message["message"]["type"],
				"text": message["message"]["text"],
				"is_customer_message": True,
				"owner": raven_channel.customer_user,
			}
		)
		doc.insert(ignore_permissions=True)

	def handle(self, message: dict) -> "RavenChannel":
		user = self.get_customer_user(user_id=message["user_id"])
		frappe.set_user(user.name)

		raven_user = self.get_raven_user(user=user, user_id=message["user_id"])
		raven_channel = self.get_raven_channel(raven_user=raven_user)
		self.create_message(raven_channel=raven_channel, message=message)

		return raven_channel
