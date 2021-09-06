#!/bin/bash

# directories
LOCKDIR=/tmp

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

export DIRENV_LOG_FORMAT=""
DIRNAME=`dirname $0`/../
cd $DIRNAME
eval "$(direnv export bash)"

python `dirname $0`/../imports/mailbox-stats.py siftware-email-recieved /home/aquarion/mail-archive/siftware-backup.mbox


# IMPORTANT: Run this first in a terminal or ssh session to go though the oauth keys
# before you add it to cron.
