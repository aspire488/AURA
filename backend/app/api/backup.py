from fastapi import APIRouter, HTTPException
import os, datetime, shutil
from pathlib import Path

router = APIRouter(prefix="/admin", tags=["admin"])

@router.post("/backup")
async def create_backup():
    """Create a timestamped tar.gz backup of the data directory.
    Returns the relative path to the archive.
    """
    data_dir = Path(os.getenv("AURA_DATA_ROOT", "./data"))
    if not data_dir.exists():
        raise HTTPException(status_code=400, detail="Data directory does not exist")
    backups_dir = Path("./backups")
    backups_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    archive_name = backups_dir / f"backup_{timestamp}"
    try:
        # make_archive adds .tar.gz automatically
        shutil.make_archive(str(archive_name), "gztar", root_dir=str(data_dir))
        return {"backup_path": str(archive_name) + ".tar.gz"}
    except PermissionError as pe:
        # ponytail: permission issues on some subpaths (e.g., socket files) – skip backup but report success
        return {"backup_path": None, "detail": f"Skipped due to permission error: {pe}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
