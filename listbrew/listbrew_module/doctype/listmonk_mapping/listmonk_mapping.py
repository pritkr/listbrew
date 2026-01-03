# Copyright (c) 2025, Prit and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class ListmonkMapping(Document):
	def after_insert(self):
		from listbrew.sync import sync_mapping_bulk
		sync_mapping_bulk(self)
