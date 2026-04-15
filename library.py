import os
import random
from typing import List, Dict

from mutagen import File


class Library:
    """Jednoduchá správa hudební knihovny podle alb."""

    SUPPORTED_EXT = (".mp3", ".ogg", ".flac", ".m4a", ".wav")
    GROUP_MODES = ("album", "artist")
    ORDER_MODES = ("alphabet", "age", "random")
    MAX_YEAR_SENTINEL = 10_000

    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        self.render_items: List[Dict] = []
        self._all_items: List[Dict] = []
        self._entries: List[Dict] = []
        self._snapshot: set[str] = set()
        self._search: str = ""
        self._group_mode: str = "album"
        self._order_mode: str = "alphabet"
        self.refresh(force=True)

    def _scan_files(self) -> List[str]:
        if not os.path.exists(self.root_dir):
            return []
        files: List[str] = []
        for name in os.listdir(self.root_dir):
            lower = name.lower()
            if any(lower.endswith(ext) for ext in self.SUPPORTED_EXT):
                files.append(name)
        return files

    def _album_name(self, filepath: str) -> str:
        try:
            audio = File(filepath)
            if audio is None or audio.tags is None:
                return "Unknown Album"
            tags = audio.tags
            if "TALB" in tags:
                try:
                    return str(tags["TALB"].text[0])
                except Exception:
                    pass
            for key in ("album", "©alb"):
                if key in tags:
                    try:
                        value = tags[key]
                        if isinstance(value, (list, tuple)):
                            return str(value[0])
                        return str(value)
                    except Exception:
                        pass
        except Exception:
            pass
        return "Unknown Album"

    def _song_name(self, filepath: str, filename: str) -> str:
        fallback = os.path.splitext(filename)[0] or filename
        try:
            audio = File(filepath)
            if audio is None or audio.tags is None:
                return fallback
            tags = audio.tags
            if "TIT2" in tags:
                try:
                    title = str(tags["TIT2"].text[0]).strip()
                    if title:
                        return title
                except Exception:
                    pass
            for key in ("title", "©nam"):
                if key in tags:
                    try:
                        value = tags[key]
                        title = str(value[0] if isinstance(value, (list, tuple)) else value).strip()
                        if title:
                            return title
                    except Exception:
                        pass
        except Exception:
            pass
        return fallback

    def _artist_name(self, filepath: str) -> str:
        try:
            audio = File(filepath)
            if audio is None or audio.tags is None:
                return "Unknown Artist"
            tags = audio.tags
            if "TPE1" in tags:
                try:
                    return str(tags["TPE1"].text[0])
                except Exception:
                    pass
            for key in ("artist", "ARTIST", "©ART"):
                if key in tags:
                    try:
                        value = tags[key]
                        if isinstance(value, (list, tuple)):
                            return str(value[0])
                        return str(value)
                    except Exception:
                        pass
        except Exception:
            pass
        return "Unknown Artist"

    @staticmethod
    def _tag_int(value) -> int | None:
        """Extract integer from common tag formats like `['2/12']`, text tags, or plain values."""
        try:
            if hasattr(value, "text"):
                value = value.text[0]
            elif isinstance(value, (list, tuple)):
                value = value[0]
            text = str(value).strip()
            if "/" in text:
                text = text.split("/", 1)[0]
            digits = "".join(ch for ch in text if ch.isdigit())
            if not digits:
                return None
            return int(digits)
        except Exception:
            return None

    def _track_number(self, filepath: str) -> int | None:
        try:
            audio = File(filepath)
            if audio is None or audio.tags is None:
                return None
            tags = audio.tags
            for key in ("TRCK", "tracknumber", "track"):
                if key in tags:
                    num = self._tag_int(tags[key])
                    if num is not None:
                        return num
        except Exception:
            pass
        return None

    def _year(self, filepath: str) -> int | None:
        try:
            audio = File(filepath)
            if audio is None or audio.tags is None:
                return None
            tags = audio.tags
            for key in ("TDRC", "TYER", "date", "year", "©day"):
                if key in tags:
                    year = self._tag_int(tags[key])
                    if year is not None and 1000 <= year <= 9999:
                        return year
        except Exception:
            pass
        return None

    def _rebuild_items(self) -> None:
        def _entry_sort_key(entry: Dict) -> tuple:
            prefix = (entry["album"].lower(),) if self._group_mode == "artist" else ()
            return prefix + (entry["track"] is None, entry["track"] or 0, entry["index"])

        groups: dict[str, List[Dict]] = {}
        for entry in self._entries:
            label = entry["artist"] if self._group_mode == "artist" else entry["album"]
            groups.setdefault(label, []).append(entry)

        group_names = list(groups.keys())
        if self._order_mode == "alphabet":
            group_names.sort(key=lambda name: name.lower())
        elif self._order_mode == "age":
            def _group_age(name: str) -> tuple[int, int, str]:
                years = [e["year"] for e in groups[name] if e.get("year") is not None]
                if years:
                    return (0, min(years), name.lower())
                # First tuple value keeps groups without year metadata after known-year groups.
                # MAX_YEAR_SENTINEL is safely above valid 4-digit years used in this app.
                return (1, self.MAX_YEAR_SENTINEL, name.lower())

            group_names.sort(key=_group_age)
        elif self._order_mode == "random":
            random.shuffle(group_names)

        items: List[Dict] = []
        for group_name in group_names:
            entries = list(groups[group_name])
            entries.sort(key=_entry_sort_key)
            items.append({"type": "album", "text": group_name})
            for entry in entries:
                items.append({
                    "type": "song",
                    "filename": entry["filename"],
                    "text": entry["song_name"],
                    "album": entry["album"],
                    "artist": entry["artist"],
                })

        self._all_items = items
        self._apply_search()

    def refresh(self, force: bool = False) -> bool:
        """Přegeneruje seznam položek, pokud se soubory změnily."""
        files = self._scan_files()
        key_set = set(files)
        if not force and key_set == self._snapshot:
            return False
        self._snapshot = key_set

        entries: List[Dict] = []
        for idx, name in enumerate(files):
            path = os.path.join(self.root_dir, name)
            entries.append({
                "index": idx,
                "filename": name,
                "song_name": self._song_name(path, name),
                "album": self._album_name(path),
                "artist": self._artist_name(path),
                "track": self._track_number(path),
                "year": self._year(path),
            })

        self._entries = entries
        self._rebuild_items()
        return True

    def set_search(self, text: str) -> None:
        self._search = text.strip().lower()
        self._apply_search()

    def set_group_mode(self, mode: str) -> None:
        mode = (mode or "").strip().lower()
        if mode not in self.GROUP_MODES:
            mode = "album"
        if mode == self._group_mode:
            return
        self._group_mode = mode
        self._rebuild_items()

    def set_order_mode(self, mode: str) -> None:
        mode = (mode or "").strip().lower()
        if mode not in self.ORDER_MODES:
            mode = "alphabet"
        if mode == self._order_mode:
            return
        self._order_mode = mode
        self._rebuild_items()

    def _apply_search(self) -> None:
        q = self._search
        if not q:
            self.render_items = list(self._all_items)
            return

        out: List[Dict] = []
        last_group: Dict | None = None
        any_for_group = False
        group_match = False

        for item in self._all_items:
            if item["type"] == "album":
                last_group = item
                any_for_group = False
                group_match = q in (item.get("text") or "").lower()
                if group_match:
                    out.append(item)
                    any_for_group = True
            else:
                text = (item.get("text") or "").lower()
                album = (item.get("album") or "").lower()
                artist = (item.get("artist") or "").lower()
                if group_match or q in text or q in album or q in artist:
                    if last_group is not None and not any_for_group:
                        out.append(last_group)
                        any_for_group = True
                    out.append(item)

        self.render_items = out
