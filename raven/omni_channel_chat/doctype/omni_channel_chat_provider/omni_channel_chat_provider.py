# Copyright (c) 2026, The Commit Company (Algocode Technologies Pvt. Ltd.) and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from .provider import FacebookProvider, InstagramProvider, LineProvider, Provider


class OmniChannelChatProvider(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		display_name: DF.Data
		fb_app_secret: DF.Password | None
		fb_page_access_token: DF.Password | None
		fb_verify_token: DF.Password | None
		ig_app_secret: DF.Password | None
		ig_page_access_token: DF.Password | None
		ig_verify_token: DF.Password | None
		line_channel_access_token: DF.Password | None
		line_channel_secret: DF.Password | None
		provider: DF.Literal["", "line", "facebook", "instagram"]
		raven_workspace: DF.Link
	# end: auto-generated types

	def decode_password_field(self):
		for field in frappe.get_meta(self.doctype).fields:
			if field.fieldtype == "Password":
				value = self.get_password(
					fieldname=field.fieldname,
					raise_exception=False,
				)
				self.set(
					key=field.fieldname,
					value=value,
				)

	def get_provider(self) -> Provider:
		if self.provider == "line":
			return LineProvider(config=self)
		elif self.provider == "facebook":
			return FacebookProvider(config=self)
		elif self.provider == "instagram":
			return InstagramProvider(config=self)
		else:
			frappe.throw(_("Provider not implemented."))


def get_omni_channel_chat(slug: str) -> OmniChannelChatProvider:
	return frappe.get_doc("Omni Channel Chat Provider", slug)
