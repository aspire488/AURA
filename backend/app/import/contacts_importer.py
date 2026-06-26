"""Contacts importer stub.

Provides a no‑op importer for contact data.
"""

from .manager import register_importer, import_records

# Register importer – identity handler
register_importer('contacts_import', '1.0', lambda rec: rec)
