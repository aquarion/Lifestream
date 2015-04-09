#!/bin/bash

# directories
LOCKDIR=/tmp
export VIRTUALENVWRAPPER_LOG_FILE=$(readlink -f `dirname $0`/../logs/venv_`basename $0`.log)

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

rm ~/Dropbox/File\ Transfer/TFL/*.png 2> /dev/null

files=`ls -1 ~/Dropbox/File\ Transfer/TFL/*.csv 2> /dev/null | wc -l`

if [[ $files == 0 ]]
then
	#echo "Nothing to do";
	exit 0
fi

source /usr/local/bin/virtualenvwrapper.sh
workon lifestream


for fle in ~/Dropbox/File\ Transfer/TFL/*.csv;
do
	echo $fle;
	python `dirname $0`/../imports/oyster_csv.py "$fle"
	mv "$fle" ~/Dropbox/File\ Transfer/TFL/complete/
done

# IMPORTANT: Run this first in a terminal or ssh session to go though the oauth keys
# before you add it to cron.
