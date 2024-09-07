#!/bin/bash

lifestream_dir=`dirname $0`/..

CSV_FILE=$lifestream_dir/datafiles/ffxiv_achievements.csv
DATABASE_FILE=$lifestream_dir/datafiles/ffxiv_achievements.db

curl -sL "https://github.com/xivapi/ffxiv-datamining/raw/master/csv/Achievement.csv" > $CSV_FILE

sed -i '1,4d' $CSV_FILE # Delete headers of achievements.csv

if [[ -f $DATABASE_FILE ]]; then
    rm $DATABASE_FILE
fi

cat $lifestream_dir/datafiles/achievements_schema.sql | sqlite3 $DATABASE_FILE

echo -e ".mode csv\n.import $CSV_FILE achievements" | sqlite3 $DATABASE_FILE 

