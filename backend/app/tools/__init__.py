from app.tools.time_tool import register as register_time
from app.tools.filesystem_tool import register as register_filesystem
from app.tools.http_tool import register as register_http
from app.tools.browser_tool import register as register_browser


def register_all():
    """Register built-in tools. ponytail: explicit list, no auto-discovery."""
    register_time()
    register_filesystem()
    register_http()
    register_browser()
