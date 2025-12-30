
// Listbrew UI Integration
frappe.ready(function () {
    const add_listbrew_button = function (frm) {
        if (frm.listbrew_button_added) return;

        frm.add_custom_button(__('Sync to Listmonk'), function () {
            frappe.call({
                method: 'listbrew.sync.sync_single_doc',
                args: {
                    doctype: frm.doc.doctype,
                    docname: frm.doc.name
                },
                freeze: true,
                freeze_message: __('Syncing to Listmonk...'),
                callback: function (r) {
                    frappe.msgprint(__('Synced successfully!'));
                }
            });
        });
        frm.listbrew_button_added = true;
    };

    let mapped_doctypes = frappe.boot.listbrew_mapped_doctypes || [];
    // Remove duplicates
    mapped_doctypes = [...new Set(mapped_doctypes)];

    mapped_doctypes.forEach(function (doctype) {
        frappe.ui.form.on(doctype, {
            refresh: function (frm) {
                if (!frm.is_new()) {
                    add_listbrew_button(frm);
                }
            }
        });
    });

    // Handle case where we are already on the page and refresh might have missed
    if (cur_frm && !cur_frm.is_new() && mapped_doctypes.includes(cur_frm.doctype)) {
        add_listbrew_button(cur_frm);
    }
});
