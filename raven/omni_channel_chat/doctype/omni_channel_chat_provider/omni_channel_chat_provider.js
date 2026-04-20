// Copyright (c) 2026, The Commit Company (Algocode Technologies Pvt. Ltd.) and contributors
// For license information, please see license.txt

frappe.ui.form.on("Omni Channel Chat Provider", {
    refresh(frm) {
        set_instagram_banner(frm);
    },
    provider(frm) {
        set_instagram_banner(frm);
    },
});

function set_instagram_banner(frm) {
    if (frm.doc.provider === "instagram") {
        frm.set_intro(__("To receive webhooks, your app must be in published state."), "yellow");
    } else {
        frm.set_intro("");
    }
}
