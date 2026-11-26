#!/bin/bash

# directories
LOCKDIR=/tmp

# Locking code based on code from http://troy.jdmz.net/cron/

# Originally by Troy Johnson,
# Adapted by Nicholas Avenell <nicholas@aquarionics.com> for lifestream.

# lock file creation and removal
LOCKFILE=$LOCKDIR/$1.lock
[ -f "$LOCKFILE" ] && echo "$LOCKFILE" exists && exit 0
trap 'rm -f "$LOCKFILE"; exit 255' 2
trap 'rm -f "$LOCKFILE"; exit 255' 15
# Preserve the real exit code instead of always reporting success, so a
# failed import is visible to cron (e.g. via its MAILTO) instead of silent.
trap 'rm -f "$LOCKFILE"' EXIT
touch "$LOCKFILE"

DIRNAME=$(dirname "$0")/../
cd "$DIRNAME" || exit 1

# $2 is optional; ${2:+...} avoids passing an empty argument when it's unset
.venv/bin/python "imports/$1.py" ${2:+"$2"}

# IMPORTANT: Run this first in a terminal or ssh session to go though the oauth keys
# before you add it to cron.
