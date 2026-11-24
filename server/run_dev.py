"""Run the server on this computer for development. Data and videos go in server/dev-data (not in git)."""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ.setdefault("KIDTUBE_DATA_DIR", str(HERE / "dev-data" / "data"))
os.environ.setdefault("KIDTUBE_LIBRARY_DIR", str(HERE / "dev-data" / "library"))
sys.path.insert(0, str(HERE))

if "KIDTUBE_FFMPEG_DIR" not in os.environ:
    import shutil

    found = shutil.which("ffmpeg")
    if not found:  # a process started outside a shell may miss the WinGet ffmpeg on the PATH
        hits = sorted(Path.home().glob("AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg*/**/bin/ffmpeg.exe"))
        found = str(hits[-1]) if hits else None
    if found:
        os.environ["KIDTUBE_FFMPEG_DIR"] = str(Path(found).parent)

import uvicorn  # noqa: E402

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8455
    uvicorn.run("app.main:app_from_env", factory=True, host="0.0.0.0", port=port)
