#!/bin/bash

# directories
LOCKDIR=/tmp
export VIRTUALENVWRAPPER_LOG_FILE=`basedir $0`/logs/venv_`basename $0`.log

# Locking code based on code from http://troy.jdmz.net/cron/

# Originally by Troy Johnson,
# Adapted by Nicholas Avenell <nicholas@aquarionics.com> for lifestream.

# lock file creation and removal
LOCKFILE=$LOCKDIR/`basename $0`.lock
[ -f $LOCKFILE ] && echo $LOCKFILE exists && exit 0
trap "{ rm -f $LOCKFILE; exit 255; }" 2
trap "{ rm -f $LOCKFILE; exit 255; }" 9
trap "{ rm -f $LOCKFILE; exit 255; }" 15
trap "{ rm -f $LOCKFILE; exit 0; }" EXIT
touch $LOCKFILE

source /usr/local/bin/virtualenvwrapper.sh
workon lifestream

python /home/aquarion/projects/lifestream/imports/github_commits.py
