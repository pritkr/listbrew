
import frappe
import listmonk
from frappe.utils import get_url

def get_listmonk_client():
    """
    Returns a configured Listmonk client based on Listbrew Settings.
    """
    settings = frappe.get_single("listbrew_settings")
    
    if not settings.enabled:
        return None

    if not settings.listmonk_url or not settings.api_username or not settings.api_password:
        frappe.log_error("Listbrew Settings are missing URL or credentials.", "Listbrew Error")
        return None

    try:
        listmonk.set_url_base(settings.listmonk_url)
        listmonk.login(settings.api_username, settings.api_password)
        return listmonk
    except Exception as e:
        frappe.log_error(f"Failed to initialize Listmonk client: {str(e)}", "Listbrew Error")
        return None

def get_safe_attributes(doc, exclude_fields=None):
    """
    Extracts safe scalar fields from a doctype for attributes mapping.
    """
    if exclude_fields is None:
        exclude_fields = []
    
    attributes = {}
    for field in doc.meta.fields:
        if field.fieldname in exclude_fields:
            continue
        
        # Only include scalar types that are safe to sync
        if field.fieldtype in ["Data", "Select", "Date", "Datetime", "Int", "Float", "Check", "Small Text"]:
            value = doc.get(field.fieldname)
            if value is not None:
                # Convert dates/datetimes to string
                if field.fieldtype in ["Date", "Datetime"]:
                    attributes[field.fieldname] = str(value)
                else:
                    attributes[field.fieldname] = value
                    
    return attributes

def boot_session(bootinfo):
    """
    Extend bootinfo with listbrew configuration.
    """
    bootinfo.listbrew_mapped_doctypes = frappe.get_all("Listmonk Mapping", filters={"sync_enabled": 1}, pluck="source_doctype")
