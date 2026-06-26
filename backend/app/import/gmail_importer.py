"""Gmail importer stub.

Provides a no‑op importer for Gmail data.
"""

from .manager import register_importer, import_records

register_importer('gmail_import', '1.0', lambda rec: rec)
