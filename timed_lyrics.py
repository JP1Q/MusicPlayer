import os
import re
from bisect import bisect_right
from dataclasses import dataclass


_TIMESTAMP_RE = re.compile(r"\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\]")
_META_TAG_RE = re.compile(r"^\[[a-zA-Z]{2,8}:[^\]]*\]\s*$")


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
            self.clear("No synchronized lyrics (.lrc) found")
            return
        try:
            lines = self.parse_lrc_text_file(lrc_path)
        except Exception:
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
        idx = bisect_right(self._times, max(0.0, float(playback_seconds))) - 1
        return idx if idx >= 0 else -1
