"""yt-dlp as a library: search, look at a URL, download one video (ADR 0004, ADR 0005).

Everything that touches the network is in this file so tests can swap it for a fake.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# H.264 + AAC in MP4, at most 1080p, so the TVs play the file directly (ADR 0005).
FORMAT = (
    "bv*[vcodec^=avc1][height<=1080]+ba[acodec^=mp4a]/"
    "b[vcodec^=avc1][height<=1080]/"
    "bv*[height<=1080]+ba/b[height<=1080]/b"
)
# <Channel> [<channel id>]/<upload date> - <title> [<video id>].mp4
OUT_TEMPLATE = (
    "%(channel,uploader|Unknown)s [%(channel_id,uploader_id|na)s]/"
    "%(upload_date>%Y-%m-%d|0000-00-00)s - %(title).100B [%(id)s].%(ext)s"
)


@dataclass
class VideoInfo:
    external_id: str
    url: str
    title: str
    duration_s: float = 0
    upload_date: str = ""
    description: str = ""
    thumb_url: str = ""
    channel_id: str = ""
    channel_title: str = ""
    is_short: bool = False
    is_live: bool = False


@dataclass
class Listing:
    """What a URL turned out to be: one video, or a list (playlist or channel)."""

    kind: str  # 'video' | 'list'
    title: str = ""
    videos: list[VideoInfo] = field(default_factory=list)
    channel_id: str = ""
    channel_url: str = ""
    avatar_url: str = ""
    description: str = ""
    is_channel: bool = False


@dataclass
class Downloaded:
    info: VideoInfo
    file_path: Path
    thumb_path: Path | None


def _thumb(e: dict) -> str:
    if e.get("thumbnail"):
        return e["thumbnail"]
    thumbs = e.get("thumbnails") or []
    return thumbs[-1].get("url", "") if thumbs else ""


def _date(e: dict) -> str:
    d = e.get("upload_date") or ""
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else ""


def _video(e: dict) -> VideoInfo:
    vid = e.get("id") or ""
    url = e.get("webpage_url") or e.get("url") or f"https://www.youtube.com/watch?v={vid}"
    return VideoInfo(
        external_id=vid,
        url=url,
        title=e.get("title") or vid,
        duration_s=float(e.get("duration") or 0),
        upload_date=_date(e),
        description=(e.get("description") or "")[:5000],
        thumb_url=_thumb(e),
        channel_id=e.get("channel_id") or e.get("uploader_id") or "",
        channel_title=e.get("channel") or e.get("uploader") or "",
        is_short="/shorts/" in url,
        is_live=(e.get("live_status") or "") in ("is_live", "is_upcoming", "was_live", "post_live"),
    )


def _avatar(res: dict) -> str:
    """A channel's round picture from its thumbnails (yt-dlp names it 'avatar_uncropped')."""
    thumbs = res.get("thumbnails") or []
    for t in thumbs:
        if "avatar" in (t.get("id") or ""):
            return t.get("url", "")
    square = [t for t in thumbs if t.get("width") and t.get("width") == t.get("height")]
    return (square[-1] if square else {}).get("url", "")


class YtDlp:
    def __init__(self, library_dir: Path, cookies_file: Path | None = None, ffmpeg_dir: str | None = None):
        self.library_dir = library_dir
        self.cookies_file = cookies_file
        self.ffmpeg_dir = ffmpeg_dir  # only needed when ffmpeg is not on the PATH

    def _opts(self, **extra) -> dict:
        # YouTube needs a JavaScript runtime to solve its player challenges; without one many videos
        # come back as "not available". deno is yt-dlp's default; node is what dev machines usually have.
        opts = {"quiet": True, "no_warnings": True, "noprogress": True, "js_runtimes": {"deno": {}, "node": {}}}
        if self.cookies_file and self.cookies_file.exists():
            opts["cookiefile"] = str(self.cookies_file)
        if self.ffmpeg_dir:
            opts["ffmpeg_location"] = self.ffmpeg_dir
        opts.update(extra)
        return opts

    def search(self, query: str, count: int = 15) -> list[VideoInfo]:
        import yt_dlp

        with yt_dlp.YoutubeDL(self._opts(extract_flat=True)) as ydl:
            res = ydl.extract_info(f"ytsearch{count}:{query}", download=False)
        return [_video(e) for e in (res.get("entries") or []) if e]

    def look(self, url: str, limit: int = 200) -> Listing:
        import yt_dlp

        with yt_dlp.YoutubeDL(self._opts(extract_flat="in_playlist", playlistend=limit)) as ydl:
            res = ydl.extract_info(url, download=False)
        if res.get("_type") in ("playlist", "multi_video"):
            videos = []
            for e in res.get("entries") or []:
                if not e:
                    continue
                if e.get("_type") == "playlist":  # a channel's tabs: flatten one level
                    videos += [_video(x) for x in (e.get("entries") or []) if x]
                else:
                    v = _video(e)
                    v.channel_id = v.channel_id or res.get("channel_id") or ""
                    v.channel_title = v.channel_title or res.get("channel") or res.get("uploader") or ""
                    videos.append(v)
            cid = res.get("channel_id") or ""
            is_channel = bool(cid) and (
                res.get("id") == cid or any(k in url for k in ("/@", "/channel/", "/c/", "/user/"))
            )
            return Listing(
                "list", res.get("channel") if is_channel and res.get("channel") else (res.get("title") or ""),
                videos[:limit], channel_id=cid, channel_url=res.get("channel_url") or "", avatar_url=_avatar(res),
                description=(res.get("description") or "")[:2000], is_channel=is_channel,
            )
        return Listing("video", res.get("title") or "", [_video(res)])

    def download(self, url: str, on_progress: Callable[[object], None] = lambda p: None) -> Downloaded:
        """Download one video. `on_progress` gets a dict per update: phase, fraction, downloaded, total, speed,
        eta. If it raises, the download stops and the exception reaches the caller (that is how Stop works)."""
        import yt_dlp

        def hook(d: dict) -> None:
            info = d.get("info_dict") or {}
            sound_only = (info.get("vcodec") or "") == "none"
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                done = d.get("downloaded_bytes") or 0
                on_progress({
                    "phase": "Downloading sound" if sound_only else "Downloading",
                    "fraction": min(0.99, done / total) if total else None,
                    "downloaded": int(done), "total": int(total),
                    "speed": float(d.get("speed") or 0), "eta": d.get("eta"),
                })
            elif d.get("status") == "finished":
                on_progress({"phase": "Downloaded the sound" if sound_only else "Downloaded the picture",
                             "fraction": None})

        def pp_hook(d: dict) -> None:
            if d.get("status") == "started":
                name = d.get("postprocessor") or ""
                on_progress({"phase": "Joining picture and sound" if name == "Merger" else "Finishing", "fraction": None})

        opts = self._opts(
            format=FORMAT,
            merge_output_format="mp4",
            outtmpl=str(self.library_dir / OUT_TEMPLATE),
            windowsfilenames=True,
            noplaylist=True,
            writethumbnail=True,
            writeinfojson=True,
            writesubtitles=True,
            subtitleslangs=["en"],
            postprocessors=[{"key": "FFmpegThumbnailsConvertor", "format": "jpg"}],
            progress_hooks=[hook],
            postprocessor_hooks=[pp_hook],
        )
        with yt_dlp.YoutubeDL(opts) as ydl:
            res = ydl.extract_info(url, download=True)
        file_path = Path(res["requested_downloads"][0]["filepath"])
        thumb = file_path.with_suffix(".jpg")
        return Downloaded(_video(res), file_path, thumb if thumb.exists() else None)

    def segments(self, video_id: str, categories: list[str]) -> list[dict]:
        """SponsorBlock segments to skip (ADR 0024). Empty when there are none or the service can't be reached."""
        import json
        import urllib.parse
        import urllib.request

        if not categories:
            return []
        q = urllib.parse.urlencode({"videoID": video_id, "categories": json.dumps(categories)})
        try:
            with urllib.request.urlopen(f"https://sponsor.ajay.app/api/skipSegments?{q}", timeout=10) as r:
                data = json.loads(r.read().decode("utf-8"))
        except Exception:  # 404 means "none"; anything else: download without skips
            return []
        out = []
        for s in data:
            start, end = (s.get("segment") or [0, 0])[:2]
            if end > start and s.get("actionType", "skip") == "skip":
                out.append({"start_s": float(start), "end_s": float(end), "category": s.get("category", "sponsor")})
        return out

    def channel_avatar(self, channel_id: str) -> tuple[str, str]:
        """(title, picture address) for one channel (ADR 0030)."""
        listing = self.look(f"https://www.youtube.com/channel/{channel_id}", limit=1)
        return listing.title, listing.avatar_url

    def fetch_image(self, url: str, max_bytes: int) -> bytes:
        """Download one picture from YouTube's image hosts. Refuses anything else or anything too big."""
        import urllib.parse
        import urllib.request

        def check(u: str) -> None:
            parts = urllib.parse.urlparse(u)
            host = parts.hostname or ""
            if parts.scheme != "https" or not host.endswith((".ggpht.com", ".ytimg.com", ".googleusercontent.com")):
                raise ValueError(f"Not a YouTube picture: {host}")

        class Redirects(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                check(newurl)  # every hop stays on YouTube's picture hosts
                return super().redirect_request(req, fp, code, msg, headers, newurl)

        check(url)
        opener = urllib.request.build_opener(Redirects)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with opener.open(req, timeout=15) as r:
            if not (r.headers.get("Content-Type") or "").startswith("image/"):
                raise ValueError("Not a picture.")
            data = r.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError("Picture too big.")
        return data

    @staticmethod
    def versions() -> dict:
        """The yt-dlp in this image and the newest on PyPI (ADR 0032: report only)."""
        import json
        import urllib.request

        from yt_dlp.version import __version__ as have

        with urllib.request.urlopen("https://pypi.org/pypi/yt-dlp/json", timeout=15) as r:
            newest = json.loads(r.read().decode("utf-8"))["info"]["version"]
        return {"have": have, "newest": newest}
