import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from timed_lyrics import TimedLyrics


class TimedLyricsTests(unittest.TestCase):
    def test_parse_lrc_text_handles_multiple_timestamps(self):
        text = "[ar:Artist]\n[00:01.00][00:02.500]Hello\n[00:03]World\n"
        lines = TimedLyrics.parse_lrc_text(text)
        self.assertEqual([round(x.time_seconds, 3) for x in lines], [1.0, 2.5, 3.0])
        self.assertEqual([x.text for x in lines], ["Hello", "Hello", "World"])

    def test_load_for_audio_missing_lrc_uses_fallback_message(self):
        with tempfile.TemporaryDirectory() as td:
            audio = Path(td) / "song.mp3"
            audio.write_bytes(b"fake")
            lyrics = TimedLyrics()
            with patch("timed_lyrics.requests.get") as mock_get:
                mock_resp = Mock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = []
                mock_get.return_value = mock_resp
                lyrics.load_for_audio(str(audio))
            self.assertEqual(lyrics.lines, [])
            self.assertIn("locally or online", lyrics.status_message)

    def test_load_for_audio_downloads_and_caches_online_lrc(self):
        with tempfile.TemporaryDirectory() as td:
            audio = Path(td) / "Artist - Song.mp3"
            audio.write_bytes(b"fake")
            lyrics = TimedLyrics()
            with patch("timed_lyrics.requests.get") as mock_get:
                mock_resp = Mock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = [{"syncedLyrics": "[00:01.00]Hello"}]
                mock_get.return_value = mock_resp
                lyrics.load_for_audio(str(audio))
            lrc_path = Path(td) / "Artist - Song.lrc"
            self.assertTrue(lrc_path.exists())
            self.assertEqual([x.text for x in lyrics.lines], ["Hello"])
            self.assertEqual(lyrics.status_message, "Lyrics loaded")

    def test_get_active_index_tracks_current_line(self):
        lyrics = TimedLyrics()
        lyrics.lines = TimedLyrics.parse_lrc_text("[00:01.00]A\n[00:04.00]B\n")
        lyrics._times = [x.time_seconds for x in lyrics.lines]
        self.assertEqual(lyrics.get_active_index(0.5), -1)
        self.assertEqual(lyrics.get_active_index(1.2), 0)
        self.assertEqual(lyrics.get_active_index(4.2), 1)


if __name__ == "__main__":
    unittest.main()
