[app]

# (str) Title of your application
title = UkasCoUmis

# (str) Package name
package.name = ukascoumis

# (str) Package domain (needed for android package identifier)
package.domain = org.ukascoumis

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include (leave empty to include all by default)
include_exts = py,png,jpg,jpeg,ttf,txt
source.exclude_dirs = build,dist,.git,.idea,.venv,__pycache__,build_workspace

# (str) Application versioning (method 1)
version = 0.1.0

# (list) Application requirements
# Keep Android requirements minimal for first working build.
# yt-dlp works without conversion if ffmpeg is not available (downloads/merges may be limited).
requirements = python3,pygame,requests,mutagen,yt-dlp

# (str) The orientation of the app
orientation = landscape

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (str) Android entry point
# For pygame projects, buildozer/p4a uses SDL2 bootstrap automatically.

# (list) Permissions
android.permissions = INTERNET

# (list) Supported architectures
# Use both to support devices that are 32-bit userspace but armv8 CPU.
android.archs = armeabi-v7a,arm64-v8a

# (int) Target Android API
android.api = 33

# (int) Minimum API your APK will support.
android.minapi = 21

# (str) Android NDK version
android.ndk = 25b

# (str) Android SDK version
android.sdk = 33

# (bool) Automatically accept Android SDK licenses during setup
android.accept_sdk_license = True

# (str) Bootstrap to use
p4a.bootstrap = sdl2

# (list) Additional p4a arguments (optional)
# p4a.extra_args =

# (str) PO4A locale folder (unused)

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug)
log_level = 2

# (str) Warn on deprecated distutils
warn_on_root = 1

# Keep build outputs in a stable project path
build_dir = .buildozer
bin_dir = build_workspace/out/android
