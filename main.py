import pygame
import os
import sys
import threading
import subprocess
import random
import io
import requests
import urllib.parse
import math
import time
try:
    import numpy as np  # numpy je jen bonus (bez něj to přežijem) x3
except Exception:
    np = None
try:
    import soundfile as sf
except Exception:
    sf = None
try:
    from pydub import AudioSegment
except Exception:
    AudioSegment = None
from mutagen import File
from pygame.locals import *

from library import Library

CUSTOM_FONT_PATH = None


def resource_path(rel_path: str) -> str:
    """Return absolute path to a resource.

    Works in dev (running from source) and in PyInstaller (files end up in
    the _internal folder / sys._MEIPASS)."""
    try:
        base = getattr(sys, "_MEIPASS")  # type: ignore[attr-defined]
        return os.path.join(base, rel_path)
    except Exception:
        return os.path.join(os.path.abspath("."), rel_path)

BG_IMAGE_PATH = "bg.png"
BG_IMAGE_ALPHA = 140


def _is_android() -> bool:
    return sys.platform in {"android"}


def _app_storage_dir() -> str | None:
    """Return writable internal app storage root on Android, else None."""
    if not _is_android():
        return None
    try:
        from android.storage import app_storage_path  # type: ignore

        return str(app_storage_path())
    except Exception:
        return None


_ANDROID_ROOT = _app_storage_dir()
LIBRARY_DIR = os.path.join(_ANDROID_ROOT, "library") if _ANDROID_ROOT else "library"
VIDEOS_DIR = os.path.join(_ANDROID_ROOT, "videos") if _ANDROID_ROOT else "videos"

if not os.path.exists(LIBRARY_DIR):
    os.makedirs(LIBRARY_DIR)
if not os.path.exists(VIDEOS_DIR):
    os.makedirs(VIDEOS_DIR)

pygame.init()
pygame.mixer.init()

# text pro UI okolo yt-dlp (status/percent) x3
yt_input_text = ""

WIDTH, HEIGHT = 1280, 720
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("UkasCoUmis MP3 Player")
clock = pygame.time.Clock()

try:
    bg_path = resource_path(BG_IMAGE_PATH)
    if os.path.exists(bg_path):
        bg_image = pygame.image.load(bg_path).convert_alpha()
        bg_image = pygame.transform.scale(bg_image, (WIDTH // 2, HEIGHT))
        bg_image.set_alpha(BG_IMAGE_ALPHA)
    else:
        bg_image = None
except Exception as e:
    bg_image = None

try:
    vol_path = resource_path("volume.png")
    if os.path.exists(vol_path):
        vol_knob_img = pygame.image.load(vol_path).convert_alpha()
        vol_knob_img = pygame.transform.smoothscale(vol_knob_img, (40, 40))
    else:
        vol_knob_img = None
except Exception:
    vol_knob_img = None

try:
    play_path = resource_path("play.png")
    play_img = pygame.image.load(play_path).convert_alpha() if os.path.exists(play_path) else None
    if play_img:
        play_img = pygame.transform.smoothscale(play_img, (40, 40))
except Exception:
    play_img = None

try:
    pause_path = resource_path("pause.png")
    pause_img = pygame.image.load(pause_path).convert_alpha() if os.path.exists(pause_path) else None
    if pause_img:
        pause_img = pygame.transform.smoothscale(pause_img, (40, 40))
except Exception:
    pause_img = None

try:
    pattern_path = resource_path("pattern.png")
    pattern_img = pygame.image.load(pattern_path).convert_alpha() if os.path.exists(pattern_path) else None
    if pattern_img:
        pattern_img = pattern_img.copy()
        pattern_img.set_alpha(40)
except Exception:
    pattern_img = None

try:
    arrow_path = resource_path("arrow.png")
    if os.path.exists(arrow_path):
        arrow_img = pygame.image.load(arrow_path).convert_alpha()
        arrow_img = pygame.transform.smoothscale(
            arrow_img,
            (max(1, int(arrow_img.get_width() * 0.42)), max(1, int(arrow_img.get_height() * 0.42)))
        )
    else:
        arrow_img = None
except Exception:
    arrow_img = None


def get_font(size):
    try:
        if CUSTOM_FONT_PATH and isinstance(CUSTOM_FONT_PATH, str) and os.path.exists(CUSTOM_FONT_PATH):
            return pygame.font.Font(CUSTOM_FONT_PATH, size)
    except Exception as e:
        pass
    try:
        return pygame.font.SysFont("comicsansms", size)
    except:
        return pygame.font.SysFont(None, size)

running = True
current_song = None
song_length = 0
is_playing = False
album_art = None
pending_art_stream = None
is_loading_metadata = False
status_msg = ""
download_status_msg = ""
download_in_progress = False
visuals = [0 for _ in range(40)]
# chaos fáze pro vizuál (ať je to ujetý) x3
visual_phase = [random.uniform(0, math.tau) for _ in range(40)]

pattern_phase = 0.0

# stav pro reálnej audio vizuál z PCM (když to jde) x3
audio_vis_lock = threading.Lock()
audio_vis_pcm: np.ndarray | None = None  # mono float32 [-1..1] x3
audio_vis_sr: int = 44100
audio_vis_ready_for: str | None = None
audio_vis_energy_smooth: float = 0.0

music_library = Library(LIBRARY_DIR)
videos_library = Library(VIDEOS_DIR)

# Volume:
# - volume_ui: what the knob shows/controls (linear 0..1)
# - mixer gain: what we send to pygame (audio-taper so % feels closer to loudness)
def _volume_ui_to_gain(x: float) -> float:
    x = float(max(0.0, min(1.0, x)))
    if x <= 0.0:
        return 0.0
    # dB-style taper (human loudness is roughly logarithmic)
    # MIN_DB controls how quiet 1% is. -45 dB is a good general taper.
    MIN_DB = -45.0
    db = MIN_DB + (0.0 - MIN_DB) * x
    return float(10.0 ** (db / 20.0))


volume_ui = 0.5
pygame.mixer.music.set_volume(_volume_ui_to_gain(volume_ui))
is_dragging_vol = False
vol_knob_center = (500, 582)
vol_knob_radius = 20
VOL_ANGLE_MIN = -135.0
VOL_ANGLE_MAX = 135.0

# Cat mosh extra state (for beat-ish bursts)
prev_energy_pat = 0.0
last_mosh_burst_ms = 0

# Posun uvnitř aktuální skladby (s)
current_offset = 0.0

dl_input_text = ""
dl_input_active = False
top_submenu = "library"  # library / download
download_step = "source"  # source -> options -> confirm
download_source = "music"  # music / videos

search_text = ""
search_active = False


show_tutorial = True
tutorial_index = 0

# alias kvůli hledání: `library` míří defaultně na music (search volá library.set_search) x3
library = music_library
LIBRARY_REFRESH_MS = 4000
next_library_refresh = 0
scroll_y = 0

was_busy = False


def _iter_section_songs(items: list[dict], section: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    current_album = None
    collapsed_set = collapsed_albums_videos if section == "videos" else collapsed_albums_music
    album_collapsed = False
    for it in items:
        if it.get("type") == "album":
            current_album = str(it.get("text") or "").strip()
            if not current_album or current_album.lower() in {"unknown", "unknown album"}:
                current_album = None
                album_collapsed = False
                continue
            album_collapsed = current_album in collapsed_set
        elif it.get("type") == "song":
            if album_collapsed:
                continue
            out.append((section, it.get("filename")))
    return out


def _get_visible_playlist() -> list[tuple[str, str]]:
    songs: list[tuple[str, str]] = []
    songs.extend(_iter_section_songs(music_library.render_items, "music"))
    songs.extend(_iter_section_songs(videos_library.render_items, "videos"))
    return [(s, f) for (s, f) in songs if f]


def _play_from_section(section: str, filename: str) -> None:
    if section == "videos":
        fp = os.path.join(VIDEOS_DIR, filename)
        if os.path.exists(fp):
            pygame.mixer.music.load(fp)
            pygame.mixer.music.play()
            _bump_play_count("videos", filename)
    else:
        play_song(filename)


def _auto_play_next_if_needed() -> None:
    global was_busy
    busy = pygame.mixer.music.get_busy()
    if was_busy and not busy and is_playing and current_song:
        pl = _get_visible_playlist()
        cur_idx = -1
        for i, (_sec, fn) in enumerate(pl):
            if fn == current_song:
                cur_idx = i
                break
        if pl and cur_idx != -1:
            nxt = pl[(cur_idx + 1) % len(pl)]
            try:
                _play_from_section(nxt[0], nxt[1])
            except Exception:
                pass
    was_busy = busy

# sbalený alba (klikem schovat/ukázat) x3
collapsed_albums_music: set[str] = set()
collapsed_albums_videos: set[str] = set()

# mini lokální stats (jen tak pro srandu) x3
STATS_PATH = "stats.json"
song_stats: dict = {}


def _load_stats():
    global song_stats
    try:
        import json
        if os.path.exists(STATS_PATH):
            with open(STATS_PATH, "r", encoding="utf-8") as f:
                song_stats = json.load(f)
    except Exception:
        song_stats = {}


def _save_stats():
    try:
        import json
        with open(STATS_PATH, "w", encoding="utf-8") as f:
            json.dump(song_stats, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _stat_key(section: str, filename: str) -> str:
    return f"{section}:{filename}"


def _bump_play_count(section: str, filename: str):
    k = _stat_key(section, filename)
    st = song_stats.get(k) or {}
    st["plays"] = int(st.get("plays", 0)) + 1
    if "rating" not in st:
        st["rating"] = random.randint(1, 5)
    song_stats[k] = st
    _save_stats()

cat_sprites: list[dict] = []
CAT_COUNT = 38
CAT_BASE_ALPHA = 35
cat_initialized = False


def _init_cat_sprites():
    global cat_sprites, cat_initialized
    if not pattern_img or cat_initialized:
        return
    cat_sprites = []
    base = pygame.transform.smoothscale(pattern_img, (int(pattern_img.get_width() * 0.45), int(pattern_img.get_height() * 0.45)))
    for _ in range(CAT_COUNT):
        cat_sprites.append({
            "x": random.uniform(HALF_W, WIDTH),
            "y": random.uniform(0, HEIGHT),
            "vx": random.uniform(-30, 30),
            "vy": random.uniform(-30, 30),
            "angle": random.uniform(0, 360),
            "spin": random.uniform(-1.8, 1.8),
            "scale": random.uniform(0.75, 1.05),
            "surf": base,
        })
    cat_initialized = True

def fetch_itunes_cover(title):
    try:
        query = os.path.splitext(title)[0].lower()
        for garbage in ["official", "video", "audio", "lyrics", "hd"]:
            query = query.replace(garbage, "")

        url = f"https://itunes.apple.com/search?term={urllib.parse.quote(query.strip())}&media=music&limit=1"
        resp = requests.get(url, timeout=3)
        data = resp.json()
        if data['resultCount'] > 0:
            img_url = data['results'][0]['artworkUrl100'].replace("100x100bb", "600x600bb")
            img_data = requests.get(img_url).content
            return io.BytesIO(img_data)
    except:
        pass
    return None

def extract_metadata(filepath):
    global song_length, pending_art_stream
    try:
        length = 0
        audio = File(filepath)
        if audio and audio.info:
            length = int(audio.info.length)
        song_length = length

        art_data = None
        if hasattr(audio, 'tags') and audio.tags:
            for tag in audio.tags.values():
                if hasattr(tag, 'data') and isinstance(tag.data, bytes):
                    art_data = tag.data
                    break
        if not art_data and hasattr(audio, 'pictures') and audio.pictures:
            art_data = audio.pictures[0].data
            
        if art_data:
            image_stream = io.BytesIO(art_data)
        else:
            image_stream = fetch_itunes_cover(os.path.basename(filepath))

        pending_art_stream = image_stream if image_stream else "CLEAR"
    except Exception as e:
        print(f"Metadata error: {e}")
        pending_art_stream = "CLEAR"

def play_song(filename):
    global current_song, is_playing, status_msg, album_art, song_length, is_loading_metadata, current_offset
    filepath = os.path.join(LIBRARY_DIR, filename)
    if os.path.exists(filepath):
        try:
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            current_song = filename
            is_playing = True
            album_art = None
            song_length = 0
            current_offset = 0.0
            is_loading_metadata = True
            threading.Thread(target=extract_metadata, args=(filepath,), daemon=True).start()
            # připrav PCM pro vizuál na pozadí (když to půjde) x3
            threading.Thread(target=_prepare_audio_vis, args=(filepath, filename), daemon=True).start()
        except Exception as e:
            status_msg = f"Can't play: {filename}"
    else:
        # když se soubor ztratil nebo se ještě zapisuje, nedržet starý výběr x3
        if current_song == filename:
            current_song = None
            is_playing = False


def seek_to_seconds(target_seconds: float):
    """Skok na danou pozici v aktuální stopě (v sekundách)."""
    global current_offset
    if not current_song or song_length <= 0:
        return
    try:
        # clamp, ať neletíme mimo stopu (pygame je pak uražený) x3
        target = max(0.0, min(float(song_length) - 0.1, float(target_seconds)))
        pygame.mixer.music.play(start=target)
        current_offset = target
    except Exception:
        # některý formáty/drivery seek neumí → tichá ignorace, žádný drama x3
        pass


def seek_relative(delta_seconds: float):
    """Relativní posun ve stopě (± sekundy)."""
    pos_now = 0.0
    if song_length > 0:
        pos_now = current_offset + max(0, pygame.mixer.music.get_pos() / 1000.0)
    seek_to_seconds(pos_now + delta_seconds)

def download_youtube(url):
    global yt_input_text, next_library_refresh, download_in_progress, download_status_msg
    old_text = yt_input_text
    yt_input_text = "Downloading: 0%"
    def yt_thread():
        global yt_input_text, next_library_refresh, download_in_progress, download_status_msg
        try:
            download_in_progress = True
            download_status_msg = "Downloading..."
            # čteme stdout od yt-dlp, ať UI vidí procenta; šablona zvládne i playlisty x3
            # NOTE: bestaudio + --restrict-filenames makes names predictable on Windows.
            # Add uploader + id to avoid collisions / wrong overwrites when titles repeat.
            cmd = [
                "yt-dlp",
                "-f", "bestaudio/best",
                "-x",
                "--audio-format", "mp3",
                "--audio-quality", "0",
                "--add-metadata",
                "--embed-thumbnail",
                "--restrict-filenames",
                "--no-overwrites",
                "--newline",
                "--progress",
                "--no-part",
                "-o", os.path.join(LIBRARY_DIR, "%(uploader)s_%(title)s_%(id)s.%(ext)s"),
                url,
            ]

            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                creationflags=creationflags,
            )

            percent = None
            last_line = ""

            if proc.stdout:
                for line in proc.stdout:
                    last_line = line.strip()
                    # Typical line contains something like: "[download]  42.3% ..."
                    if "[download]" in last_line and "%" in last_line:
                        # Best-effort parse the first token that ends with '%'
                        tokens = last_line.replace("\t", " ").split()
                        for tok in tokens:
                            if tok.endswith("%"):
                                percent = tok
                                break

                    if percent:
                        yt_input_text = f"Downloading: {percent}"
                        download_status_msg = yt_input_text
                    else:
                        yt_input_text = "Downloading..."
                        download_status_msg = yt_input_text

                    # během stahování občas refresh knihovny (playlisty se sypou postupně) x3
                    if "[ExtractAudio]" in last_line or "Destination" in last_line or "Downloading item" in last_line:
                        next_library_refresh = 0

            rc = proc.wait()
            if rc != 0:
                yt_input_text = old_text
                download_status_msg = "Download failed"
                download_in_progress = False
                return

            yt_input_text = ""
            download_status_msg = "Download completed"

            # po konci chvilku čekáme (ffmpeg/thumbnail), pak refresh x3
            try:
                import time
                time.sleep(0.6)
            except Exception:
                pass

            next_library_refresh = 0
            download_in_progress = False
        except Exception:
            yt_input_text = old_text
            download_status_msg = "Download error"
            download_in_progress = False
    threading.Thread(target=yt_thread, daemon=True).start()


def download_youtube_video_audio(url):
    """Download audio from videos into VIDEOS_DIR."""
    global yt_input_text, next_library_refresh, download_in_progress, download_status_msg
    old_text = yt_input_text
    yt_input_text = "Downloading (video): 0%"

    def yt_thread():
        global yt_input_text, next_library_refresh, download_in_progress, download_status_msg
        try:
            download_in_progress = True
            download_status_msg = "Downloading (video)..."
            cmd = [
                "yt-dlp",
                "-f", "bestaudio/best",
                "-x",
                "--audio-format", "mp3",
                "--audio-quality", "0",
                "--add-metadata",
                "--embed-thumbnail",
                "--restrict-filenames",
                "--no-overwrites",
                "--newline",
                "--progress",
                "--no-part",
                "-o", os.path.join(VIDEOS_DIR, "%(uploader)s_%(title)s_%(id)s.%(ext)s"),
                url,
            ]

            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                creationflags=creationflags,
            )

            percent = None
            if proc.stdout:
                for line in proc.stdout:
                    last_line = line.strip()
                    if "[download]" in last_line and "%" in last_line:
                        tokens = last_line.replace("\t", " ").split()
                        for tok in tokens:
                            if tok.endswith("%"):
                                percent = tok
                                break
                    if percent:
                        yt_input_text = f"Downloading (video): {percent}"
                        download_status_msg = yt_input_text
                    else:
                        yt_input_text = "Downloading (video)..."
                        download_status_msg = yt_input_text

                    if "[ExtractAudio]" in last_line or "Destination" in last_line or "Downloading item" in last_line:
                        next_library_refresh = 0

            rc = proc.wait()
            if rc != 0:
                yt_input_text = old_text
                download_status_msg = "Download failed"
                download_in_progress = False
                return

            yt_input_text = ""
            download_status_msg = "Download completed"
            time.sleep(0.6)
            next_library_refresh = 0
            download_in_progress = False
        except Exception:
            yt_input_text = old_text
            download_status_msg = "Download error"
            download_in_progress = False

    threading.Thread(target=yt_thread, daemon=True).start()


def reset_download_flow(clear_url: bool = False) -> None:
    global download_step, dl_input_active, dl_input_text
    download_step = "source"
    dl_input_active = False
    if clear_url:
        dl_input_text = ""


def start_download_from_flow() -> None:
    global top_submenu
    u = dl_input_text.strip()
    if not u or "http" not in u:
        return

    if download_source == "videos":
        download_youtube_video_audio(u)
    else:
        download_youtube(u)

    reset_download_flow(clear_url=True)
    top_submenu = "library"

HALF_W = WIDTH // 2
ART_RECT = pygame.Rect((HALF_W - 480) // 2, 50, 480, 480)
PLAY_BTN = pygame.Rect(HALF_W // 2 - 30 - 40, 560, 40, 45)
PAUSE_BTN = pygame.Rect(HALF_W // 2 + 30, 560, 40, 45)
PROGRESS_BAR_RECT = pygame.Rect(80, 640, 480, 8)
SEARCH_RECT = pygame.Rect(HALF_W + 180, 18, 260, 26)
TOP_SUBMENU_LIBRARY_RECT = pygame.Rect(HALF_W + 20, 16, 74, 28)
TOP_SUBMENU_DOWNLOAD_RECT = pygame.Rect(TOP_SUBMENU_LIBRARY_RECT.right + 8, 16, 96, 28)
DL_SOURCE_MUSIC_RECT = pygame.Rect(HALF_W + 36, 120, 210, 42)
DL_SOURCE_VIDEOS_RECT = pygame.Rect(HALF_W + 264, 120, 210, 42)
DL_INPUT_RECT = pygame.Rect(HALF_W + 36, 205, 438, 32)
DL_BACK_BTN_RECT = pygame.Rect(HALF_W + 36, 258, 90, 34)
DL_CANCEL_BTN_RECT = pygame.Rect(HALF_W + 136, 258, 95, 34)
DL_NEXT_BTN_RECT = pygame.Rect(HALF_W + 241, 258, 95, 34)
DL_CONFIRM_BTN_RECT = pygame.Rect(HALF_W + 346, 258, 128, 34)

# Rects used for tutorial targeting (so the arrow points to actual UI elements)
LIBRARY_LIST_RECT = pygame.Rect(HALF_W + 20, 60, HALF_W - 40, HEIGHT - 200)

tutorial_font = get_font(26)

tutorial_steps = [
    {
        "text": "1. Vyber skladbu vpravo v knihovně a kliknutím ji spusť.",
        # Target the library list area (not a hard-coded pixel that may land on background art)
        "target": "library",
        "side": "right",
    },
    {
        "text": "2. Tady je obal alba a jednoduchý vizuál.",
        "target": "art",
        "side": "top",
    },
    {
        "text": "3. Středové tlačítko přepíná přehrávání / pauzu.",
        "target": "play",
        "side": "top",
    },
    {
        "text": "4. Časová osa dole – kliknutím přeskočíš v rámci tracku.",
        "target": "progress",
        "side": "top",
    },
    {
        "text": "5. Nahoře otevři Download a projdi kroky source -> options -> confirm.",
        "target": "download_menu",
        "side": "top",
    },
    {
        "text": "6. Pole 'hledat' filtruje knihovnu podle názvu alba nebo skladby.",
        "target": "search",
        "side": "bottom",
    },
]


def _tutorial_target_rect(step: dict) -> pygame.Rect:
    t = step.get("target")
    if t == "library":
        return LIBRARY_LIST_RECT
    if t == "art":
        return ART_RECT
    if t == "play":
        return PLAY_BTN
    if t == "progress":
        return PROGRESS_BAR_RECT
    if t == "youtube":
        return DL_INPUT_RECT
    if t == "download_menu":
        return TOP_SUBMENU_DOWNLOAD_RECT
    if t == "search":
        return SEARCH_RECT
    # Fallback if someone adds a step without target
    return pygame.Rect(WIDTH // 2, HEIGHT // 2, 1, 1)


def _tutorial_arrow_pose(step: dict) -> tuple[tuple[int, int], float]:
    """Return (center_pos, angle_deg) for arrow image.

    Convention used here: arrow.png points UP at 0 degrees.
    """
    rect = _tutorial_target_rect(step)
    side = step.get("side", "right")
    pad = int(step.get("pad", 70))

    # Tip point on the target element
    if side == "left":
        tip = rect.midleft
        center = (rect.left - pad, rect.centery)
    elif side == "right":
        tip = rect.midright
        center = (rect.right + pad, rect.centery)
    elif side == "top":
        tip = rect.midtop
        center = (rect.centerx, rect.top - pad)
    elif side == "bottom":
        tip = rect.midbottom
        center = (rect.centerx, rect.bottom + pad)
    else:
        tip = rect.center
        center = (rect.right + pad, rect.centery)

    dx = tip[0] - center[0]
    dy = tip[1] - center[1]
    # Compute direction from arrow center -> tip (target)
    # atan2 gives 0° pointing RIGHT; pygame.rotate is CCW with screen y down.
    angle_deg = -math.degrees(math.atan2(dy, dx))

    # Calibrate arrow asset orientation.
    # Try both common conventions: arrow points UP at 0° or points RIGHT at 0°.
    # We'll pick the one that makes the arrow point *most* toward the target.
    angle_up0 = angle_deg - 90
    angle_right0 = angle_deg

    # Decide which calibration is closer by comparing unit vectors
    def score(a: float) -> float:
        rad = math.radians(-a)
        vx, vy = math.cos(rad), math.sin(rad)
        # desired vector
        mag = math.hypot(dx, dy) or 1.0
        tx, ty = dx / mag, dy / mag
        return vx * tx + vy * ty  # dot product

    angle_deg = angle_up0 if score(angle_up0) >= score(angle_right0) else angle_right0

    # If the sprite is still mirrored (some arrow art has tail->tip opposite), allow optional flip.
    if step.get("flip", False):
        angle_deg += 180

    return (int(center[0]), int(center[1])), float(angle_deg)

title_font = get_font(24)
info_font = get_font(20)


def _prepare_audio_vis(filepath: str, key: str) -> None:
    """Decode audio file to mono float32 PCM for FFT visualization."""
    global audio_vis_pcm, audio_vis_sr, audio_vis_ready_for
    if np is None:
        return
    try:
        # Prefer soundfile for wav/flac/ogg etc.
        pcm = None
        sr = 44100
        if sf is not None:
            try:
                data, sr = sf.read(filepath, always_2d=True, dtype="float32")
                pcm = data.mean(axis=1)
            except Exception:
                pcm = None

        # Fallback to pydub (handles mp3 if ffmpeg is available)
        if pcm is None and AudioSegment is not None:
            seg = AudioSegment.from_file(filepath)
            sr = seg.frame_rate
            arr = np.array(seg.get_array_of_samples())
            if seg.channels > 1:
                arr = arr.reshape((-1, seg.channels)).mean(axis=1)
            # normalize based on sample width
            maxv = float(1 << (8 * seg.sample_width - 1))
            pcm = (arr.astype(np.float32) / maxv)

        if pcm is None:
            return

        with audio_vis_lock:
            audio_vis_pcm = pcm
            audio_vis_sr = int(sr)
            audio_vis_ready_for = key
    except Exception:
        # Keep visualization optional
        return

# simple audio buffer visualizer (best-effort): capture small chunks of audio output is not trivial in pygame.
# We'll approximate "real" reaction by using get_pos() and a deterministic pseudo signal combined with volume.
# If numpy is available (it is), we can make smooth beat-ish motion synced to playback time.
def get_music_energy():
    """RMS energy from real PCM if available, else fallback to time-synced signal."""
    global audio_vis_energy_smooth
    if not (is_playing and pygame.mixer.music.get_busy()):
        audio_vis_energy_smooth *= 0.9
        return audio_vis_energy_smooth

    # Try real PCM
    if np is not None:
        with audio_vis_lock:
            pcm = audio_vis_pcm
            sr = audio_vis_sr
            ready_for = audio_vis_ready_for
        if pcm is not None and ready_for == current_song and sr > 0:
            t = current_offset + max(0.0, pygame.mixer.music.get_pos() / 1000.0)
            idx = int(t * sr)
            win = int(sr * 0.06)  # 60ms window
            a = max(0, idx - win)
            b = min(len(pcm), idx + win)
            if b > a + 16:
                chunk = pcm[a:b]
                rms = float(np.sqrt(np.mean(chunk * chunk)))
                energy = rms * 300.0
                audio_vis_energy_smooth = audio_vis_energy_smooth * 0.85 + energy * 0.15
                return audio_vis_energy_smooth

    # Fallback: deterministic pseudo-signal tied to playback time
    t = (current_offset + max(0.0, pygame.mixer.music.get_pos() / 1000.0))
    e = abs(math.sin(t * 2.6)) * 60 + abs(math.sin(t * 7.4)) * 25
    audio_vis_energy_smooth = audio_vis_energy_smooth * 0.85 + (e * (0.5 + volume_ui)) * 0.15
    return audio_vis_energy_smooth

while running:
    mouse_pos = pygame.mouse.get_pos()
    mouse_click = False

    now_ms = pygame.time.get_ticks()
    if now_ms >= next_library_refresh:
        music_library.refresh()
        videos_library.refresh()
        next_library_refresh = now_ms + LIBRARY_REFRESH_MS

    _init_cat_sprites()

    if pending_art_stream:
        if pending_art_stream != "CLEAR":
            try:
                raw_art = pygame.image.load(pending_art_stream).convert_alpha()
                w, h = raw_art.get_size()
                min_dim = min(w, h)
                x = (w - min_dim) // 2
                y = (h - min_dim) // 2
                square_surf = raw_art.subsurface((x, y, min_dim, min_dim))
                album_art = pygame.transform.smoothscale(square_surf, (480, 480))
                pygame.display.set_icon(album_art)
            except:
                album_art = None
        pending_art_stream = None
        is_loading_metadata = False

    for event in pygame.event.get():
        if event.type == QUIT:
            running = False
            
        elif event.type == MOUSEBUTTONDOWN:
            if event.button == 1:
                dist = math.hypot(mouse_pos[0] - vol_knob_center[0], mouse_pos[1] - vol_knob_center[1])
                if dist <= vol_knob_radius:
                    is_dragging_vol = True
                else:
                    mouse_click = True
            elif event.button == 4:
                if mouse_pos[0] > HALF_W:
                    scroll_y = max(scroll_y - 20, 0)
            elif event.button == 5:
                if mouse_pos[0] > HALF_W:
                    scroll_y += 20

        elif event.type == KEYDOWN:
            if show_tutorial:
                if event.key == K_RIGHT:
                    if tutorial_index < len(tutorial_steps) - 1:
                        tutorial_index += 1
                elif event.key == K_LEFT:
                    if tutorial_index > 0:
                        tutorial_index -= 1
                elif event.key in (K_RETURN, K_ESCAPE):
                    show_tutorial = False
            elif top_submenu == "download" and event.key == K_ESCAPE:
                reset_download_flow()
                top_submenu = "library"
            elif top_submenu == "download" and download_step == "confirm":
                if event.key == K_RETURN:
                    start_download_from_flow()
                elif event.key == K_BACKSPACE:
                    download_step = "options"
                    dl_input_active = True
            elif dl_input_active:
                if event.key == K_RETURN:
                    u = dl_input_text.strip()
                    if u and "http" in u:
                        download_step = "confirm"
                        dl_input_active = False
                elif event.key == K_v and (event.mod & KMOD_CTRL):
                    try:
                        import pygame.scrap
                        if not pygame.scrap.get_init():
                            pygame.scrap.init()
                        data = pygame.scrap.get(SCRAP_TEXT)
                        if data:
                            text = data.decode("utf-8", errors="ignore").replace("\x00", "")
                            filtered = "".join(ch for ch in text if ch >= " " and ch != "\x7f")
                            dl_input_text += filtered
                    except Exception:
                        pass
                elif event.key == K_BACKSPACE:
                    dl_input_text = dl_input_text[:-1]
                else:
                    ch = event.unicode
                    if ch and ch >= " " and ch != "\x7f":
                        dl_input_text += ch
            elif search_active and top_submenu == "library":
                if event.key == K_RETURN:
                    pass
                elif event.key == K_BACKSPACE:
                    search_text = search_text[:-1]
                    library.set_search(search_text)
                else:
                    ch = event.unicode
                    if ch and ch >= " " and ch != "\x7f":
                        search_text += ch
                        library.set_search(search_text)
            else:
                if event.key == K_SPACE:
                    playing_now = is_playing and pygame.mixer.music.get_busy()
                    if current_song:
                        if playing_now:
                            pygame.mixer.music.pause()
                        else:
                            if pygame.mixer.music.get_pos() < 0:
                                play_song(current_song)
                            else:
                                pygame.mixer.music.unpause()
                elif event.key == K_RIGHT:
                    seek_relative(5.0)
                elif event.key == K_LEFT:
                    seek_relative(-5.0)

        elif event.type == MOUSEBUTTONUP:
            if event.button == 1:
                is_dragging_vol = False
                
        elif event.type == MOUSEMOTION:
            if is_dragging_vol:
                # lineární ovládání hlasitosti podle úhlu kolem knoflíku x3
                mx, my = mouse_pos
                ang = math.degrees(math.atan2(my - vol_knob_center[1], mx - vol_knob_center[0]))
                # převod úhlu na rozsah 0..1 (clamp)
                ang = max(VOL_ANGLE_MIN, min(VOL_ANGLE_MAX, ang))
                volume_ui = (ang - VOL_ANGLE_MIN) / (VOL_ANGLE_MAX - VOL_ANGLE_MIN)
                volume_ui = max(0.0, min(1.0, float(volume_ui)))
                pygame.mixer.music.set_volume(_volume_ui_to_gain(volume_ui))

    pygame.draw.rect(screen, (210, 210, 210), (0, 0, HALF_W, HEIGHT))
    pygame.draw.rect(screen, (235, 235, 235), (HALF_W, 0, HALF_W, HEIGHT))

    if bg_image:
        screen.blit(bg_image, (HALF_W, 0))

    # Random cat sprites background (moshpit physics + reacts to energy)
    if cat_sprites:
        dt = clock.get_time() / 1000.0
        dt = max(0.0, min(0.05, dt))

        energy_pat = get_music_energy()
        alpha = int(CAT_BASE_ALPHA + min(140.0, energy_pat * 0.45))
        wobble = math.sin(pattern_phase) * (1.0 + energy_pat * 0.006)
        pattern_phase += 0.08 if (is_playing and pygame.mixer.music.get_busy()) else 0.02

        # mosh constants (centrum vpravo, ať to neschová obal) x3
        cx, cy = HALF_W + (HALF_W * 0.5), HEIGHT * 0.55
        accel = 95.0 + energy_pat * 1.1
        damp = 0.975
        kick = 190.0 + energy_pat * 1.8
        # Smaller radius => cats can get closer / overlap more
        rad = 14.0

        # random impulses
        playing_busy = is_playing and pygame.mixer.music.get_busy()
        if playing_busy and random.random() < (0.18 + min(0.20, energy_pat * 0.00025)):
            p = random.choice(cat_sprites)
            ang = random.uniform(0, math.tau)
            p["vx"] += math.cos(ang) * kick
            p["vy"] += math.sin(ang) * kick

        # occasional "hit" when energy jumps (cheap beat-ish burst)
        now_ms = pygame.time.get_ticks()
        if playing_busy:
            if (energy_pat - prev_energy_pat) > 140.0 and (now_ms - last_mosh_burst_ms) > 180:
                last_mosh_burst_ms = now_ms
                burst_n = random.randint(3, 7)
                for _ in range(burst_n):
                    p = random.choice(cat_sprites)
                    ang = random.uniform(0, math.tau)
                    p["vx"] += math.cos(ang) * (kick * random.uniform(0.9, 1.3))
                    p["vy"] += math.sin(ang) * (kick * random.uniform(0.9, 1.3))
        prev_energy_pat = energy_pat

        # pairwise collisions (cheap enough for 38 cats)
        for i in range(len(cat_sprites)):
            a = cat_sprites[i]
            for j in range(i + 1, len(cat_sprites)):
                b = cat_sprites[j]
                dx = b["x"] - a["x"]
                dy = b["y"] - a["y"]
                d2 = dx * dx + dy * dy
                min_d = rad * 2
                if d2 > 0.0001 and d2 < (min_d * min_d):
                    d = math.sqrt(d2)
                    nx, ny = dx / d, dy / d
                    # separate them
                    push = (min_d - d) * 0.5
                    a["x"] -= nx * push
                    a["y"] -= ny * push
                    b["x"] += nx * push
                    b["y"] += ny * push
                    # bounce velocities
                    rel = (b["vx"] - a["vx"]) * nx + (b["vy"] - a["vy"]) * ny
                    if rel < 0:
                        imp = -rel * 1.05
                        a["vx"] -= nx * imp
                        a["vy"] -= ny * imp
                        b["vx"] += nx * imp
                        b["vy"] += ny * imp

        for c in cat_sprites:
            # pull toward center + wobble
            dx = cx - c["x"]
            dy = cy - c["y"]
            mag = math.hypot(dx, dy) or 1.0
            c["vx"] += (dx / mag) * accel * dt + wobble * 14.0 * dt
            c["vy"] += (dy / mag) * accel * dt - wobble * 12.0 * dt

            # integrate
            c["x"] += c["vx"] * dt
            c["y"] += c["vy"] * dt

            # walls bounce (držet ve vpravo části) x3
            if c["x"] < HALF_W:
                c["x"] = HALF_W
                c["vx"] *= -0.9
            elif c["x"] > WIDTH:
                c["x"] = WIDTH
                c["vx"] *= -0.9
            if c["y"] < 0:
                c["y"] = 0
                c["vy"] *= -0.9
            elif c["y"] > HEIGHT:
                c["y"] = HEIGHT
                c["vy"] *= -0.9

            c["vx"] *= damp
            c["vy"] *= damp

            # spin harder with energy
            c["angle"] += c["spin"] + (energy_pat * 0.02) + (abs(c["vx"]) + abs(c["vy"])) * 0.0035

            surf = c["surf"]
            # apply per-sprite alpha
            s = surf.copy()
            s.set_alpha(max(0, min(255, alpha)))
            # scale + rotate
            # NOTE: smoothscale/rotation can create bright/white fringes on transparent PNG edges.
            # Using nearest-ish scaling here reduces halo artifacts a lot.
            if c["scale"] != 1.0:
                sw = max(1, int(s.get_width() * c["scale"]))
                sh = max(1, int(s.get_height() * c["scale"]))
                s = pygame.transform.scale(s, (sw, sh))
            r = pygame.transform.rotate(s, c["angle"])
            rect = r.get_rect(center=(int(c["x"]), int(c["y"])))
            screen.blit(r, rect.topleft)

    pygame.draw.rect(screen, (225, 225, 225), ART_RECT, border_radius=15)
    if album_art:
        energy = sum(visuals) / len(visuals) if visuals else 0
        jitter = min(6, int(energy * 0.06))
        off_x = random.randint(-jitter, jitter) if jitter > 0 else 0
        off_y = random.randint(-jitter, jitter) if jitter > 0 else 0

        art_rect = ART_RECT.move(off_x, off_y)

        surface = pygame.Surface(ART_RECT.size, SRCALPHA)
        pygame.draw.rect(surface, (255, 255, 255, 255), surface.get_rect(), border_radius=15)
        album_surface = album_art.copy()
        album_surface.blit(surface, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        screen.blit(album_surface, art_rect.topleft)
    else:
        placeholder_text = "Loading Album Art..." if is_loading_metadata else "album cover here x3"
        lbl = title_font.render(placeholder_text, True, (150, 150, 150))
        screen.blit(lbl, (ART_RECT.centerx - lbl.get_width()//2, ART_RECT.centery - lbl.get_height()//2))

    is_music_busy = pygame.mixer.music.get_busy()
    bar_w = (ART_RECT.width // len(visuals)) - 2
    vis_start_x = ART_RECT.x
    vis_start_y = 620

    # Make lines react to music energy (time-synced), not purely random
    energy = get_music_energy()

    for i in range(len(visuals)):
        # advance each bar's phase; faster when playing, slower when idle
        visual_phase[i] += (0.10 + (energy * 0.0006)) if (is_playing and is_music_busy) else 0.03

        if is_playing and is_music_busy:
            # Deterministic per-bar response based on energy + phase
            base = 6 + (energy * 0.35)
            wobble = (math.sin(visual_phase[i] + i * 0.35) * (6 + energy * 0.06))
            target = max(0.0, base + wobble)
            visuals[i] += (target - visuals[i]) * 0.22
        else:
            visuals[i] += (0 - visuals[i]) * 0.12

        # Funny jitter / sway per bar
        jitter_x = int(math.sin(visual_phase[i] * 1.7) * (1 + energy * 0.01))
        jitter_h = visuals[i] + (math.sin(visual_phase[i] * 2.3) * 4)
        jitter_h = max(0.0, jitter_h)

        if jitter_h > 1:
            # When playing, make the bars “turn around” (swing) with energy.
            # We'll draw each bar on a small surface and rotate it.
            if is_playing and is_music_busy:
                swing = math.sin(visual_phase[i]) * min(35.0, 8.0 + energy * 0.08)
                bar_surf = pygame.Surface((bar_w, int(jitter_h)), pygame.SRCALPHA)
                pygame.draw.rect(bar_surf, (180, 180, 180), (0, 0, bar_w, int(jitter_h)))
                rot = pygame.transform.rotate(bar_surf, swing)
                # anchor bottom to baseline
                x = vis_start_x + i * (bar_w + 2) + jitter_x
                y = vis_start_y
                r = rot.get_rect(midbottom=(x + bar_w // 2, y))
                screen.blit(rot, r.topleft)
            else:
                pygame.draw.rect(
                    screen,
                    (180, 180, 180),
                    (vis_start_x + i * (bar_w + 2) + jitter_x, vis_start_y - jitter_h, bar_w, jitter_h),
                )

    playing_now = is_playing and pygame.mixer.music.get_busy()

    if play_img and pause_img:
        img = pause_img if playing_now else play_img
        btn_rect = img.get_rect(center=PLAY_BTN.center)
        screen.blit(img, btn_rect.topleft)
    else:
        if playing_now:
            pygame.draw.rect(screen, (0, 0, 0), (PLAY_BTN.x, PLAY_BTN.y, 8, PLAY_BTN.height), border_radius=3)
            pygame.draw.rect(screen, (0, 0, 0), (PLAY_BTN.x + 18, PLAY_BTN.y, 8, PLAY_BTN.height), border_radius=3)
        else:
            pygame.draw.polygon(screen, (0, 0, 0), [
                (PLAY_BTN.x, PLAY_BTN.y),
                (PLAY_BTN.x + PLAY_BTN.width, PLAY_BTN.y + PLAY_BTN.height // 2),
                (PLAY_BTN.x, PLAY_BTN.y + PLAY_BTN.height)
            ], 3)

    if mouse_click:
        if PLAY_BTN.collidepoint(mouse_pos) and current_song:
            if playing_now:
                pygame.mixer.music.pause()
            else:
                if pygame.mixer.music.get_pos() < 0:
                    play_song(current_song)
                else:
                    pygame.mixer.music.unpause()

    if vol_knob_img:
        # lineární mapování volume -> úhel knoflíku x3
        angle_deg = VOL_ANGLE_MAX - (volume_ui * (VOL_ANGLE_MAX - VOL_ANGLE_MIN))
        rotated_knob = pygame.transform.rotate(vol_knob_img, angle_deg)
        knob_rect = rotated_knob.get_rect(center=vol_knob_center)
        screen.blit(rotated_knob, knob_rect.topleft)
    else:
        pygame.draw.circle(screen, (0, 0, 0), vol_knob_center, vol_knob_radius, 3)
        angle = -math.pi * 0.75 + (volume_ui * math.pi * 1.5)
        end_x = vol_knob_center[0] + math.sin(angle) * (vol_knob_radius - 4)
        end_y = vol_knob_center[1] - math.cos(angle) * (vol_knob_radius - 4)
        pygame.draw.line(screen, (0, 0, 0), vol_knob_center, (end_x, end_y), 4)

    vol_text = info_font.render(f"Vol: {int(volume_ui*100)}%", True, (100, 100, 100))
    screen.blit(vol_text, (vol_knob_center[0] - vol_text.get_width()//2, vol_knob_center[1] + vol_knob_radius + 5))

    # Progress bar: always visible (neon blue background + pink progress)
    NEON_BLUE = (0, 240, 255)
    NEON_PINK = (255, 60, 200)
    pygame.draw.rect(screen, NEON_BLUE, PROGRESS_BAR_RECT, border_radius=4)
    pygame.draw.rect(screen, (0, 0, 0), PROGRESS_BAR_RECT, 2, border_radius=4)

    curr_time_str = "0:00"
    total_time_str = "0:00"
    if current_song and song_length > 0:
        pos_s = current_offset + max(0, pygame.mixer.music.get_pos() / 1000.0)
        if pos_s < 0:
            pos_s = 0
        if pos_s > song_length:
            pos_s = song_length
        fill_w = int((pos_s / song_length) * PROGRESS_BAR_RECT.width)
        pygame.draw.rect(
            screen,
            NEON_PINK,
            (PROGRESS_BAR_RECT.x, PROGRESS_BAR_RECT.y, fill_w, PROGRESS_BAR_RECT.height),
            border_radius=4,
        )
        curr_time_str = f"{int(pos_s) // 60}:{int(pos_s) % 60:02d}"
        total_time_str = f"{song_length // 60}:{song_length % 60:02d}"

    time_text = info_font.render(f"{curr_time_str}/{total_time_str}", True, (50, 50, 50))
    screen.blit(time_text, (PROGRESS_BAR_RECT.right - time_text.get_width(), PROGRESS_BAR_RECT.bottom + 5))

    if mouse_click and current_song and song_length > 0 and PROGRESS_BAR_RECT.collidepoint(mouse_pos):
        rel = (mouse_pos[0] - PROGRESS_BAR_RECT.x) / PROGRESS_BAR_RECT.width
        rel = max(0.0, min(1.0, rel))
        seek_to_seconds(rel * song_length)
    # Top submenu (Library / Download)
    if mouse_click and TOP_SUBMENU_LIBRARY_RECT.collidepoint(mouse_pos):
        top_submenu = "library"
        dl_input_active = False
    elif mouse_click and TOP_SUBMENU_DOWNLOAD_RECT.collidepoint(mouse_pos):
        top_submenu = "download"
        search_active = False

    lib_btn_col = (255, 255, 255) if top_submenu == "library" else (228, 228, 228)
    dl_btn_col = (255, 255, 255) if top_submenu == "download" else (228, 228, 228)
    pygame.draw.rect(screen, lib_btn_col, TOP_SUBMENU_LIBRARY_RECT, border_radius=8)
    pygame.draw.rect(screen, (170, 170, 170), TOP_SUBMENU_LIBRARY_RECT, 1, border_radius=8)
    pygame.draw.rect(screen, dl_btn_col, TOP_SUBMENU_DOWNLOAD_RECT, border_radius=8)
    pygame.draw.rect(screen, (170, 170, 170), TOP_SUBMENU_DOWNLOAD_RECT, 1, border_radius=8)
    screen.blit(info_font.render("Library", True, (40, 40, 40)), (TOP_SUBMENU_LIBRARY_RECT.x + 7, TOP_SUBMENU_LIBRARY_RECT.y + 3))
    screen.blit(info_font.render("Download", True, (40, 40, 40)), (TOP_SUBMENU_DOWNLOAD_RECT.x + 7, TOP_SUBMENU_DOWNLOAD_RECT.y + 3))

    # Library/download panel
    lib_area = pygame.Rect(HALF_W + 10, 45, HALF_W - 20, HEIGHT - 250)
    lib_overlay = pygame.Surface((lib_area.width, lib_area.height), pygame.SRCALPHA)
    lib_overlay.fill((255, 255, 255, 35))
    screen.blit(lib_overlay, lib_area.topleft)

    if top_submenu == "library":
        old_clip = screen.get_clip()
        screen.set_clip(pygame.Rect(HALF_W + 20, 60, HALF_W - 40, HEIGHT - 260))

        y_offset = 60 - scroll_y

        def draw_section(items, section_name: str, enabled: bool, x0: int, y: int) -> int:
            global current_song, is_playing
            if not enabled:
                return y

            collapsed_set = collapsed_albums_videos if section_name == "videos" else collapsed_albums_music
            current_album: str | None = None
            album_collapsed = False

            for item in items:
                if item["type"] == "album":
                    current_album = str(item.get("text") or "").strip()
                    if not current_album or current_album.lower() in {"unknown", "unknown album"}:
                        current_album = None
                        album_collapsed = False
                        continue
                    album_collapsed = current_album in collapsed_set

                    # album header row with toggle
                    tri = ">" if album_collapsed else "v"
                    header_rect = pygame.Rect(x0, y, HALF_W - 60, 30)

                    # click toggle
                    if mouse_click and header_rect.collidepoint(mouse_pos):
                        if album_collapsed:
                            collapsed_set.discard(current_album)
                            album_collapsed = False
                        else:
                            collapsed_set.add(current_album)
                            album_collapsed = True

                    lbl = title_font.render(f"{tri} {current_album}", True, (50, 50, 50))
                    screen.blit(lbl, (x0, y))
                    y += 35
                elif item["type"] == "song":
                    # skip songs if current album is collapsed
                    if current_album is not None and album_collapsed:
                        continue
                    song = item["filename"]
                    song_rect = pygame.Rect(x0 + 20, y, HALF_W - 60, 30)
                    color = (0, 0, 0)

                    if song == current_song:
                        color = (100, 150, 255)
                    elif song_rect.collidepoint(mouse_pos):
                        color = (100, 100, 100)
                        if mouse_click:
                            # Switch library root based on section
                            if section_name == "videos":
                                # play from videos folder
                                fp = os.path.join(VIDEOS_DIR, song)
                                if os.path.exists(fp):
                                    try:
                                        pygame.mixer.music.load(fp)
                                        pygame.mixer.music.play()
                                        current_song = song
                                        is_playing = True
                                        _bump_play_count("videos", song)
                                    except Exception:
                                        pass
                            else:
                                play_song(song)

                    st = song_stats.get(_stat_key(section_name, song)) or {}
                    plays = int(st.get("plays", 0))
                    rating = int(st.get("rating", 0))
                    stat_txt = ""
                    if rating:
                        stat_txt += f"  {'*' * rating}"
                    if plays:
                        stat_txt += f"  {plays} plays"
                    s_lbl = info_font.render(f"{item['text']}{stat_txt}", True, color)
                    screen.blit(s_lbl, (song_rect.x, song_rect.y))
                    y += 35

            return y

        # Always show both sections with separators
        header_h = 26
        screen.blit(info_font.render("Music", True, (60, 60, 60)), (HALF_W + 24, y_offset))
        y_offset += header_h
        y_offset = draw_section(music_library.render_items, "music", True, HALF_W + 20, y_offset)
        y_offset += 18
        screen.blit(info_font.render("Videos", True, (60, 60, 60)), (HALF_W + 24, y_offset))
        y_offset += header_h
        y_offset = draw_section(videos_library.render_items, "videos", True, HALF_W + 20, y_offset)

        screen.set_clip(old_clip)

        if mouse_click:
            search_active = SEARCH_RECT.collidepoint(mouse_pos)
        dl_input_active = False

        search_caption = info_font.render("hledat:", True, (50, 50, 50))
        screen.blit(search_caption, (HALF_W + 120, 20))

        s_color = (255, 255, 255) if search_active else (230, 230, 230)
        pygame.draw.rect(screen, s_color, SEARCH_RECT)
        pygame.draw.rect(screen, (180, 180, 180), SEARCH_RECT, 1)

        s_surf = info_font.render(search_text or "alb nebo song", True, (120, 120, 120) if not search_text else (0, 0, 0))
        s_x = SEARCH_RECT.x + 5
        if s_surf.get_width() > SEARCH_RECT.width - 10:
            s_x -= (s_surf.get_width() - (SEARCH_RECT.width - 10))
        old_clip = screen.get_clip()
        screen.set_clip(SEARCH_RECT)
        screen.blit(s_surf, (s_x, SEARCH_RECT.y + 3))
        screen.set_clip(old_clip)
    else:
        search_active = False

        flow_title = title_font.render("Download flow", True, (50, 50, 50))
        screen.blit(flow_title, (HALF_W + 24, 66))

        step_hint = info_font.render(f"Step: {download_step}  (source -> options -> confirm)", True, (75, 75, 75))
        screen.blit(step_hint, (HALF_W + 24, 96))

        if download_in_progress and download_status_msg:
            d = info_font.render(download_status_msg, True, (80, 80, 80))
            screen.blit(d, (HALF_W + 24, 326))

        if download_step == "source":
            src_lbl = info_font.render("Choose source folder:", True, (45, 45, 45))
            screen.blit(src_lbl, (HALF_W + 24, 170))

            src_music_color = (255, 255, 255) if download_source == "music" else (236, 236, 236)
            src_video_color = (255, 255, 255) if download_source == "videos" else (236, 236, 236)
            pygame.draw.rect(screen, src_music_color, DL_SOURCE_MUSIC_RECT, border_radius=8)
            pygame.draw.rect(screen, (170, 170, 170), DL_SOURCE_MUSIC_RECT, 1, border_radius=8)
            pygame.draw.rect(screen, src_video_color, DL_SOURCE_VIDEOS_RECT, border_radius=8)
            pygame.draw.rect(screen, (170, 170, 170), DL_SOURCE_VIDEOS_RECT, 1, border_radius=8)
            screen.blit(info_font.render("Music", True, (30, 30, 30)), (DL_SOURCE_MUSIC_RECT.x + 74, DL_SOURCE_MUSIC_RECT.y + 8))
            screen.blit(info_font.render("Videos", True, (30, 30, 30)), (DL_SOURCE_VIDEOS_RECT.x + 72, DL_SOURCE_VIDEOS_RECT.y + 8))

            if mouse_click:
                if DL_SOURCE_MUSIC_RECT.collidepoint(mouse_pos):
                    download_source = "music"
                    download_step = "options"
                    dl_input_active = True
                elif DL_SOURCE_VIDEOS_RECT.collidepoint(mouse_pos):
                    download_source = "videos"
                    download_step = "options"
                    dl_input_active = True
        elif download_step == "options":
            dl_lbl = info_font.render(f"Source: {download_source}. Paste YouTube URL:", True, (50, 50, 50))
            screen.blit(dl_lbl, (DL_INPUT_RECT.x, DL_INPUT_RECT.y - 25))

            if mouse_click:
                if DL_BACK_BTN_RECT.collidepoint(mouse_pos):
                    download_step = "source"
                    dl_input_active = False
                elif DL_CANCEL_BTN_RECT.collidepoint(mouse_pos):
                    reset_download_flow()
                    top_submenu = "library"
                elif DL_NEXT_BTN_RECT.collidepoint(mouse_pos) and dl_input_text.strip() and "http" in dl_input_text.strip():
                    download_step = "confirm"
                    dl_input_active = False
                else:
                    dl_input_active = DL_INPUT_RECT.collidepoint(mouse_pos)

            input_color = (200, 200, 200) if not dl_input_active else (255, 255, 255)
            pygame.draw.rect(screen, input_color, DL_INPUT_RECT)
            pygame.draw.rect(screen, (180, 180, 180), DL_INPUT_RECT, 1)

            rendered_input = info_font.render(dl_input_text, True, (0, 0, 0))
            txt_x = DL_INPUT_RECT.x + 5
            if rendered_input.get_width() > DL_INPUT_RECT.width - 10:
                txt_x -= (rendered_input.get_width() - (DL_INPUT_RECT.width - 10))
            old_clip = screen.get_clip()
            screen.set_clip(DL_INPUT_RECT)
            screen.blit(rendered_input, (txt_x, DL_INPUT_RECT.y + 3))
            screen.set_clip(old_clip)

            pygame.draw.rect(screen, (235, 235, 235), DL_BACK_BTN_RECT, border_radius=8)
            pygame.draw.rect(screen, (180, 180, 180), DL_BACK_BTN_RECT, 1, border_radius=8)
            pygame.draw.rect(screen, (235, 235, 235), DL_CANCEL_BTN_RECT, border_radius=8)
            pygame.draw.rect(screen, (180, 180, 180), DL_CANCEL_BTN_RECT, 1, border_radius=8)
            next_col = (235, 235, 235) if dl_input_text.strip() and "http" in dl_input_text.strip() else (205, 205, 205)
            pygame.draw.rect(screen, next_col, DL_NEXT_BTN_RECT, border_radius=8)
            pygame.draw.rect(screen, (180, 180, 180), DL_NEXT_BTN_RECT, 1, border_radius=8)
            screen.blit(info_font.render("Back", True, (30, 30, 30)), (DL_BACK_BTN_RECT.x + 23, DL_BACK_BTN_RECT.y + 6))
            screen.blit(info_font.render("Cancel", True, (30, 30, 30)), (DL_CANCEL_BTN_RECT.x + 16, DL_CANCEL_BTN_RECT.y + 6))
            screen.blit(info_font.render("Next", True, (30, 30, 30)), (DL_NEXT_BTN_RECT.x + 23, DL_NEXT_BTN_RECT.y + 6))
        else:
            preview_url = dl_input_text.strip() or "-"
            src = info_font.render(f"Source: {download_source}", True, (45, 45, 45))
            url = info_font.render(f"URL: {preview_url[:55]}", True, (45, 45, 45))
            confirm_hint = info_font.render("Confirm download?", True, (45, 45, 45))
            screen.blit(src, (HALF_W + 24, 165))
            screen.blit(url, (HALF_W + 24, 196))
            screen.blit(confirm_hint, (HALF_W + 24, 227))

            if mouse_click:
                if DL_BACK_BTN_RECT.collidepoint(mouse_pos):
                    download_step = "options"
                    dl_input_active = True
                elif DL_CANCEL_BTN_RECT.collidepoint(mouse_pos):
                    reset_download_flow()
                    top_submenu = "library"
                elif DL_CONFIRM_BTN_RECT.collidepoint(mouse_pos):
                    start_download_from_flow()

            pygame.draw.rect(screen, (235, 235, 235), DL_BACK_BTN_RECT, border_radius=8)
            pygame.draw.rect(screen, (180, 180, 180), DL_BACK_BTN_RECT, 1, border_radius=8)
            pygame.draw.rect(screen, (235, 235, 235), DL_CANCEL_BTN_RECT, border_radius=8)
            pygame.draw.rect(screen, (180, 180, 180), DL_CANCEL_BTN_RECT, 1, border_radius=8)
            pygame.draw.rect(screen, (235, 235, 235), DL_CONFIRM_BTN_RECT, border_radius=8)
            pygame.draw.rect(screen, (180, 180, 180), DL_CONFIRM_BTN_RECT, 1, border_radius=8)
            screen.blit(info_font.render("Back", True, (30, 30, 30)), (DL_BACK_BTN_RECT.x + 23, DL_BACK_BTN_RECT.y + 6))
            screen.blit(info_font.render("Cancel", True, (30, 30, 30)), (DL_CANCEL_BTN_RECT.x + 16, DL_CANCEL_BTN_RECT.y + 6))
            screen.blit(info_font.render("Download", True, (30, 30, 30)), (DL_CONFIRM_BTN_RECT.x + 17, DL_CONFIRM_BTN_RECT.y + 6))

    if show_tutorial:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        screen.blit(overlay, (0, 0))

        step = tutorial_steps[tutorial_index]
        if arrow_img:
            arrow_center, angle = _tutorial_arrow_pose(step)
            arr = pygame.transform.rotate(arrow_img, angle)
            rect = arr.get_rect(center=arrow_center)
            screen.blit(arr, rect.topleft)

        text = step["text"]
        wrapped = []
        words = text.split(" ")
        line = ""
        for w in words:
            test = (line + " " + w).strip()
            surf = tutorial_font.render(test, True, (255, 255, 255))
            if surf.get_width() > WIDTH - 80 and line:
                wrapped.append(line)
                line = w
            else:
                line = test
        if line:
            wrapped.append(line)

        y = HEIGHT - 120
        for l in wrapped:
            surf = tutorial_font.render(l, True, (255, 255, 255))
            screen.blit(surf, (40, y))
            y += surf.get_height() + 4

        # Page indicator (e.g. 3/6)
        page = info_font.render(f"{tutorial_index + 1}/{len(tutorial_steps)}", True, (230, 230, 230))
        screen.blit(page, (WIDTH - page.get_width() - 20, HEIGHT - 40))

        # Hint text (ASCII-friendly so it renders reliably)
        hint_text = "Arrow keys Left/Right: next step | Enter/Esc: close"
        hint = info_font.render(hint_text, True, (210, 210, 210))
        screen.blit(hint, (40, HEIGHT - 40))

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()
