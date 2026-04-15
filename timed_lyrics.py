import os
import re
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

try:
    from mutagen import File as MutagenFile
except ImportError:
    MutagenFile = None


_TIMESTAMP_RE = re.compile(r"\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\]")
_META_TAG_RE = re.compile(r"^\[[a-zA-Z]{2,8}:[^\]]*\]\s*$")
_LRCLIB_SEARCH_URL = "https://lrclib.net/api/search"


@dataclass(frozen=True)
class LyricLine:
    time_seconds: float
    text: str


class TimedLyrics:
    def __init__(self) -> None:
        self.lines: list[LyricLine] = []
        self._times: list[float] = []
        self.source_path: str | None = None
        self.status_message: str = "No lyrics loaded"

    def clear(self, status_message: str = "No lyrics loaded") -> None:
        self.lines = []
        self._times = []
        self.source_path = None
        self.status_message = status_message

    def load_for_audio(self, audio_path: str | None) -> None:
        if not audio_path:
            self.clear("No track selected")
            return
        lrc_path = os.path.splitext(audio_path)[0] + ".lrc"
        if not os.path.exists(lrc_path):
            if not self._download_and_cache_lrc(audio_path, lrc_path):
                self.clear("No synchronized lyrics (.lrc) found locally or online")
                return
        try:
            lines = self.parse_lrc_text_file(lrc_path)
        except (OSError, UnicodeError):
            self.clear("Failed to parse lyrics file")
            return
        if not lines:
            self.clear("Lyrics file has no timed lines")
            return
        self.lines = lines
        self._times = [line.time_seconds for line in lines]
        self.source_path = lrc_path
        self.status_message = "Lyrics loaded"

    @staticmethod
    def parse_lrc_text_file(path: str) -> list[LyricLine]:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return TimedLyrics.parse_lrc_text(f.read())

    @staticmethod
    def parse_lrc_text(text: str) -> list[LyricLine]:
        out: list[LyricLine] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if _META_TAG_RE.match(line):
                continue
            matches = list(_TIMESTAMP_RE.finditer(line))
            if not matches:
                continue
            lyric_text = _TIMESTAMP_RE.sub("", line).strip()
            for m in matches:
                minutes = int(m.group(1))
                seconds = int(m.group(2))
                milliseconds_str = m.group(3) or "0"
                millis = int(milliseconds_str.ljust(3, "0")[:3])
                total = minutes * 60 + seconds + (millis / 1000.0)
                out.append(LyricLine(time_seconds=total, text=lyric_text))
        out.sort(key=lambda x: x.time_seconds)
        return out

    def get_active_index(self, playback_seconds: float) -> int:
        if not self._times:
            return -1
        idx = bisect_right(self._times, max(0.0, playback_seconds)) - 1
        return idx if idx >= 0 else -1

    @staticmethod
    def _guess_artist_title(audio_path: str) -> tuple[str | None, str | None]:
        stem = Path(audio_path).stem.strip()
        artist = None
        title = stem or None
        if " - " in stem:
            left, right = stem.split(" - ", 1)
            if left.strip() and right.strip():
                artist = left.strip()
                title = right.strip()

        if MutagenFile is None:
            return artist, title
        try:
            audio = MutagenFile(audio_path, easy=True)
            tags = getattr(audio, "tags", None) or {}
            tag_title = tags.get("title", [None])[0]
            tag_artist = tags.get("artist", [None])[0]
            if isinstance(tag_title, str) and tag_title.strip():
                title = tag_title.strip()
            if isinstance(tag_artist, str) and tag_artist.strip():
                artist = tag_artist.strip()
        except Exception:
            pass
        return artist, title

    @staticmethod
    def _pick_synced_lyrics(payload: object) -> str | None:
        if not isinstance(payload, list):
            return None
        for item in payload:
            if not isinstance(item, dict):
                continue
            synced = item.get("syncedLyrics")
            if isinstance(synced, str) and synced.strip():
                return synced.strip()
        return None

    def _download_and_cache_lrc(self, audio_path: str, lrc_path: str) -> bool:
        if requests is None:
            return False
        artist, title = self._guess_artist_title(audio_path)
        stem = Path(audio_path).stem.strip()
        candidates: list[dict[str, str]] = []
        if title and artist:
            candidates.append({"track_name": title, "artist_name": artist})
        if title:
            candidates.append({"track_name": title})
        if stem and stem != title:
            candidates.append({"track_name": stem})

        for params in candidates:
            try:
                resp = requests.get(_LRCLIB_SEARCH_URL, params=params, timeout=3)
                if resp.status_code != 200:
                    continue
                synced = self._pick_synced_lyrics(resp.json())
                if not synced:
                    continue
                with open(lrc_path, "w", encoding="utf-8") as f:
                    f.write(synced.rstrip() + "\n")
                return True
            except Exception:
                continue
        return False
