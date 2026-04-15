import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

if "mutagen" not in sys.modules:
    mock_mutagen = types.ModuleType("mutagen")
    mock_mutagen.File = lambda *_args, **_kwargs: None
    sys.modules["mutagen"] = mock_mutagen

import library as library_module


Library = library_module.Library


class _MockAlbumTag:
    def __init__(self, value):
        self.text = [value]


class _Audio:
    def __init__(self, tags):
        self.tags = tags


def _create_mock_audio_file_loader(album_by_file):
    def _load_mock_audio(path):
        filename = os.path.basename(path)
        value = album_by_file.get(filename)
        if isinstance(value, Exception):
            raise value
        if value is None:
            return None
        if isinstance(value, dict):
            return _Audio(value)
        return _Audio({"album": [value]})

    return _load_mock_audio


class LibraryTests(unittest.TestCase):
    def test_refresh_groups_by_album_and_sorts(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("b.mp3", "a.mp3", "z.ogg", "ignore.txt"):
                with open(os.path.join(tmp, name), "wb"):
                    pass

            with patch.object(library_module, "File", side_effect=_create_mock_audio_file_loader({
                "a.mp3": "Alpha",
                "z.ogg": "Alpha",
                "b.mp3": "Beta",
            })):
                lib = Library(tmp)

            self.assertEqual(
                lib.render_items,
                [
                    {"type": "album", "text": "Alpha"},
                    {"type": "song", "filename": "a.mp3", "text": "a"},
                    {"type": "song", "filename": "z.ogg", "text": "z"},
                    {"type": "album", "text": "Beta"},
                    {"type": "song", "filename": "b.mp3", "text": "b"},
                ],
            )

    def test_set_search_keeps_matching_album_and_song(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("a.mp3", "b.mp3"):
                with open(os.path.join(tmp, name), "wb"):
                    pass

            with patch.object(library_module, "File", side_effect=_create_mock_audio_file_loader({
                "a.mp3": "Alpha",
                "b.mp3": "Beta",
            })):
                lib = Library(tmp)

            lib.set_search("b")

            self.assertEqual(
                lib.render_items,
                [
                    {"type": "album", "text": "Beta"},
                    {"type": "song", "filename": "b.mp3", "text": "b"},
                ],
            )

    def test_refresh_returns_false_when_snapshot_is_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "a.mp3"), "wb"):
                pass

            with patch.object(library_module, "File", return_value=None):
                lib = Library(tmp)

            with patch.object(lib, "_album_name", wraps=lib._album_name) as mock_album_name:
                self.assertFalse(lib.refresh())
                mock_album_name.assert_not_called()

            with patch.object(lib, "_album_name", wraps=lib._album_name) as mock_album_name:
                self.assertTrue(lib.refresh(force=True))
                mock_album_name.assert_called_once()

    def test_album_name_prefers_talb_then_falls_back_to_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(library_module, "File", return_value=None):
                lib = Library(tmp)

            with patch.object(library_module, "File", return_value=_Audio({"TALB": _MockAlbumTag("Album From TALB")})):
                self.assertEqual(lib._album_name("any.mp3"), "Album From TALB")

            with patch.object(library_module, "File", return_value=_Audio({"album": ["Album Fallback"]})):
                self.assertEqual(lib._album_name("any.mp3"), "Album Fallback")

            with patch.object(library_module, "File", side_effect=RuntimeError("read error")):
                self.assertEqual(lib._album_name("any.mp3"), "Unknown Album")

    def test_album_name_uses_playlist_metadata_when_album_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(library_module, "File", return_value=None):
                lib = Library(tmp)

            with patch.object(library_module, "File", return_value=_Audio({"TXXX:PLAYLIST": _MockAlbumTag("Rory in Early 20s")})):
                self.assertEqual(lib._album_name("any.mp3"), "Rory in Early 20s")

            with patch.object(library_module, "File", return_value=_Audio({"TXXX:playlist": _MockAlbumTag("Live Set")})):
                self.assertEqual(lib._album_name("any.mp3"), "Live Set")

    def test_album_name_prefers_album_tag_over_playlist_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(library_module, "File", return_value=None):
                lib = Library(tmp)

            with patch.object(library_module, "File", return_value=_Audio({
                "album": ["Studio Album"],
                "TXXX:PLAYLIST": _MockAlbumTag("Playlist Name"),
            })):
                self.assertEqual(lib._album_name("any.mp3"), "Studio Album")


if __name__ == "__main__":
    unittest.main()
