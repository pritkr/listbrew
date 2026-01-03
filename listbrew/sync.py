
import frappe
import os
import csv
import json
import tempfile
from pathlib import Path
from frappe.utils import get_site_path
from listbrew.utils import get_listmonk_client, get_safe_attributes

def sync_scheduled():
    """
    Scheduled job to sync all enabled mappings.
    """
    settings = frappe.get_single("listbrew_settings")
    if not settings.enabled:
        return

    # Check background job interval if needed, or just run if enabled.
    # For simplicity/MVP, we run if enabled and rely on scheduler frequency (e.g. hourly).
    
    mappings = frappe.get_all("Listmonk Mapping", filters={"sync_enabled": 1}, fields=["*"])
    for mapping in mappings:
        try:
            mapping_doc = frappe.get_doc("Listmonk Mapping", mapping.name)
            sync_mapping_bulk(mapping_doc)
        except Exception as e:
            frappe.log_error(f"Error syncing mapping {mapping.name}: {str(e)}", "Listbrew Sync Error")

@frappe.whitelist()
def sync_mapping_bulk_manual(mapping_name):
    """
    Wrapper for manual trigger from UI.
    """
    mapping_doc = frappe.get_doc("Listmonk Mapping", mapping_name)
    return sync_mapping_bulk(mapping_doc)

def sync_mapping_bulk(mapping_doc):
    """
    Performs bulk sync for a specific mapping configuration.
    """
    client = get_listmonk_client()
    if not client:
        return False

    source_doctype = mapping_doc.source_doctype
    # Handle list_id as list of ints (comma separated string)
    raw_list_ids = mapping_doc.listmonk_list_id or ""
    list_ids = [int(x.strip()) for x in raw_list_ids.split(",") if x.strip()]

    email_field = mapping_doc.email_field
    name_field = mapping_doc.name_field

    # Fetch data
    fields = [email_field, name_field]
    # Add primary key 'name' to fields to identify doc
    if 'name' not in fields:
        fields.append('name')
        
    data = frappe.get_all(source_doctype, fields=fields)
    
    if not data:
        return True

    # Prepare CSV
    # Listmonk import expects: email, name, attributes (JSON)
    # We will exclude email and name field from attributes
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as tmp_file:
        writer = csv.writer(tmp_file)
        # Write header
        writer.writerow(['email', 'name', 'attributes'])
        
        for row in data:
            email = row.get(email_field)
            if not email:
                continue
                
            name = row.get(name_field) or ""
            
            # Get full doc to extract all attributes
            # Optimisation: Might be slow for huge datasets to get_doc for each.
            # But for attributes we need full doc or we select all fields in get_all.
            # Let's try to get safe attributes from the row if possible, 
            # but row only has selected fields. 
            # For bulk import, maybe we fetch all fields in get_all?
            # Let's fetch the full doc for now to be safe and correct.
            doc = frappe.get_doc(source_doctype, row['name'])
            attributes = get_safe_attributes(doc, exclude_fields=[email_field, name_field])
            
            writer.writerow([email, name, json.dumps(attributes)])
            
        tmp_path = tmp_file.name

    try:
        # Call import
        # lists argument expects a list of int
        result = client.import_subscribers(
            file_path=Path(tmp_path),
            mode='subscribe',
            delim=',',
            lists=list_ids,
            overwrite=True
        )
        frappe.msgprint(f"Started import for {source_doctype}. Status: {result}")
        return result
    except Exception as e:
        frappe.log_error(f"Listmonk Import Error: {str(e)}", "Listbrew Sync Error")
        return False
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

def sync_subscriber_realtime(doc, method=None):
    """
    Realtime sync handler for on_update event.
    """
    # Check if this doctype is mapped
    mapping_name = frappe.db.get_value("Listmonk Mapping", {"source_doctype": doc.doctype, "sync_enabled": 1}, "name")
    if not mapping_name:
        return

    mapping_doc = frappe.get_doc("Listmonk Mapping", mapping_name)
    
    client = get_listmonk_client()
    if not client:
        return

    email = doc.get(mapping_doc.email_field)
    if not email:
        return

    name = doc.get(mapping_doc.name_field) or ""
    attributes = get_safe_attributes(doc, exclude_fields=[mapping_doc.email_field, mapping_doc.name_field])
    
    # Parse list IDs
    raw_list_ids = mapping_doc.listmonk_list_id or ""
    target_list_ids = {int(x.strip()) for x in raw_list_ids.split(",") if x.strip()}

    try:
        # Check if subscriber exists
        subscriber = client.subscriber_by_email(email)
        
        if subscriber:
            # Update
            subscriber.name = name
            subscriber.attribs.update(attributes)
            
            client.update_subscriber(subscriber, target_list_ids, set())
        else:
            # Create
            client.create_subscriber(
                email,
                name,
                target_list_ids,
                pre_confirm=bool(mapping_doc.pre_confirm_subscriptions),
                attribs=attributes
            )
    except Exception as e:
        frappe.log_error(f"Realtime sync failed for {doc.name}: {str(e)}", "Listbrew Sync Error")

def delete_subscriber_realtime(doc, method=None):
    """
    Realtime sync handler for on_trash event.
    """
    mapping_name = frappe.db.get_value("Listmonk Mapping", {"source_doctype": doc.doctype, "sync_enabled": 1}, "name")
    if not mapping_name:
        return

    mapping_doc = frappe.get_doc("Listmonk Mapping", mapping_name)
    client = get_listmonk_client()
    if not client:
        return

    email = doc.get(mapping_doc.email_field)
    if not email:
        # Check if email changed? In on_trash we have the doc about to be deleted.
        return

    try:
        subscriber = client.subscriber_by_email(email)
        if subscriber:
             action = mapping_doc.on_delete_in_frappe
             if action == "Unsubscribe in listmonk":
                 client.block_subscriber(subscriber)
             else:
                 # Default to "Delete in listmonk"
                 client.delete_subscriber(subscriber.email)
    except Exception as e:
        frappe.log_error(f"Delete sync failed for {doc.name}: {str(e)}", "Listbrew Sync Error")

@frappe.whitelist()
def sync_single_doc(doctype, docname):
    """
    Manual sync for a single document from UI button.
    """
    doc = frappe.get_doc(doctype, docname)
    sync_subscriber_realtime(doc)
    return True
