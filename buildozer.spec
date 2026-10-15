[app]
title = Shadow Fighter
package.name = shadowfighter
package.domain = com.shadowfighter
source.dir = .
source.include_exts = py,png,ogg
version = 1.0
requirements = python3,pygame,pyjnius
orientation = landscape
fullscreen = 1
icon.filename = %(source.dir)s/icon.png
android.api = 33
android.minapi = 21
android.archs = arm64-v8a, armeabi-v7a
android.release_artifact = aab
android.debug_artifact = apk
android.permissions = INTERNET,ACCESS_NETWORK_STATE
android.enable_androidx = True
android.gradle_dependencies = com.google.android.gms:play-services-ads:22.6.0
android.meta_data = com.google.android.gms.ads.APPLICATION_ID=ca-app-pub-3940256099942544~3347511713

[buildozer]
log_level = 2
warn_on_root = 1
