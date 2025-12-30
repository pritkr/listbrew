
frappe.ui.form.on('Listmonk Mapping', {
    refresh: function (frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__('Sync Now'), function () {
                frappe.call({
                    method: 'listbrew.sync.sync_mapping_bulk_manual',
                    args: {
                        mapping_name: frm.doc.name
                    },
                    freeze: true,
                    freeze_message: __('Syncing...'),
                    callback: function (r) {
                        if (r.message) {
                            frappe.msgprint(__('Sync started successfully. Check logs/import status.'));
                        }
                    }
                });
            });
        }
    }
});
