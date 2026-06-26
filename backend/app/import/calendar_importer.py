"""Google Calendar Takeout JSON importer.

Provides a stub importer that does nothing.
"""

from .manager import register_importer, import_records

# Register importer – identity handler (no processing)
register_importer('calendar_import', '1.0', lambda rec: rec)
