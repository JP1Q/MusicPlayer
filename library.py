import os
from typing import List, Dict

from mutagen import File


class Library:
    """Jednoduchá správa hudební knihovny podle alb."""

    SUPPORTED_EXT = (".mp3", ".ogg", ".flac", ".m4a", ".wav")

    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        self.render_items: List[Dict] = []
        self._all_items: List[Dict] = []
        self._snapshot: set[str] = set()
        self._search: str = ""
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

    def refresh(self, force: bool = False) -> bool:
        """Přegeneruje seznam položek, pokud se soubory změnily."""
        files = self._scan_files()
        key_set = set(files)
        if not force and key_set == self._snapshot:
            return False
        self._snapshot = key_set

        groups: dict[str, list[tuple[str, str]]] = {}
        for name in files:
            path = os.path.join(self.root_dir, name)
            album = self._album_name(path)
            song_name = self._song_name(path, name)
            groups.setdefault(album, []).append((song_name, name))

        items: List[Dict] = []
        for album in sorted(groups.keys()):
            items.append({"type": "album", "text": album})
            for song_name, filename in sorted(groups[album], key=lambda x: x[0].lower()):
                items.append({"type": "song", "filename": filename, "text": song_name})

        self._all_items = items
        self._apply_search()
        return True

    def set_search(self, text: str) -> None:
        self._search = text.strip().lower()
        self._apply_search()

    def _apply_search(self) -> None:
        q = self._search
        if not q:
            self.render_items = list(self._all_items)
            return

        out: List[Dict] = []
        last_album: Dict | None = None
        any_for_album = False

        for item in self._all_items:
            if item["type"] == "album":
                # flush předchozí album pokud mělo zásah
                if last_album is not None and any_for_album:
                    out.append(last_album)
                last_album = item
                any_for_album = False
            else:
                text = (item.get("text") or "").lower()
                if q in text:
                    if last_album is not None and not any_for_album:
                        out.append(last_album)
                        any_for_album = True
                    out.append(item)

        # poslední album
        if last_album is not None and any_for_album and last_album not in out:
            out.insert(0, last_album)

        self.render_items = out

