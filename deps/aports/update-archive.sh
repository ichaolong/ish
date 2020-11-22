#!/bin/sh -x
# This script only works on my machine
function sync_repo() {
    version="$1"
    path="$2"
    rclone copy -v --transfers=32 "alpine:$version/$path" "b2:alpine-archive/$path"
    date=$(date +%F)
    rclone moveto "b2:alpine-archive/$path/APKINDEX.tar.gz" "b2:alpine-archive/$path/APKINDEX-$version-$date.tar.gz"
}
sync_repo v3.12 main/x86
sync_repo v3.12 community/x86
