import asyncio

import frappe
from werkzeug.wrappers import Response

from raven.omni_channel_chat.doctype.omni_channel_chat_provider.omni_channel_chat_provider import (
	get_omni_channel_chat,
)


def extract_slug() -> str:
	"""Extract the trailing path segment (slug) from the current request URL.

	Strips a trailing slash if present, then returns the last path component.
	Used by webhook handlers to identify which Omni Channel Chat Provider configuration
	should process the incoming request.

	Returns:
		str: The slug portion of the request path.

	Example:
		For a request to `/api/method/raven.omni_channel_chat.api.webhooks.line/g9ju6k0e8r`,
		this returns `g9ju6k0e8r`.
	"""
	request = frappe.local.request
	return request.path.rstrip("/").rsplit("/", 1)[-1]


@frappe.whitelist(allow_guest=True, methods=["POST"])
def line() -> dict:
	slug = extract_slug()
	request = frappe.local.request
	body: bytes = request.get_data()
	headers: dict = dict(request.headers)

	omni_channel_chat = get_omni_channel_chat(slug=slug)
	provider = omni_channel_chat.get_provider()
	asyncio.run(provider.handle_webhook(body=body, headers=headers))
	return {"status": "ok"}


@frappe.whitelist(allow_guest=True, methods=["GET", "POST"])
def facebook() -> dict | Response | None:
	slug = extract_slug()
	request = frappe.local.request

	omni_channel_chat = get_omni_channel_chat(slug=slug)
	provider = omni_channel_chat.get_provider()

	if request.method == "GET":
		mode = frappe.form_dict.get("hub.mode")
		verify_token = frappe.form_dict.get("hub.verify_token")
		challenge = frappe.form_dict.get("hub.challenge", "0")

		if mode == "subscribe" and verify_token == provider._verify_token:
			return Response(challenge, status=200, content_type="text/plain")
		else:
			frappe.throw("Verification failed", frappe.PermissionError)

	body: bytes = request.get_data()
	headers: dict = dict(request.headers)

	asyncio.run(provider.handle_webhook(body=body, headers=headers))
	return {"status": "ok"}
