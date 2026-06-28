import sys
import pathlib

# Ensure the backend/app package is on the import path
_project_root = pathlib.Path(__file__).parent.parent
_backend_root = _project_root / "backend"
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

# Point this package to the actual backend/app directory
__path__ = [str(_backend_root / "app")]
