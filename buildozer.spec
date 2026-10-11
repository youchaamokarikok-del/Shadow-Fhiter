[app]
title = Shadow Fighter
package.name = shadowfighter
package.domain = com.shadowfighter
source.dir = .
source.include_exts = py,png,ogg
version = 1.0
requirements = python3,pygame
orientation = landscape
fullscreen = 1
icon.filename = %(source.dir)s/icon.png
android.api = 33
android.minapi = 21
android.archs = arm64-v8a, armeabi-v7a
android.release_artifact = aab
android.debug_artifact = apk

[buildozer]
log_level = 2
warn_on_root = 1
