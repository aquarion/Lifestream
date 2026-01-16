#!/bin/bash

lifestream_dir=$(dirname $0)/..

CSV_FILE=$lifestream_dir/datafiles/ffxiv_achievements.csv
DATABASE_FILE=$lifestream_dir/datafiles/ffxiv_achievements.db
URL="https://raw.githubusercontent.com/xivapi/ffxiv-datamining/master/csv/en/Achievement.csv"

rm -f $CSV_FILE

curl --fail-with-body -sL $URL >$CSV_FILE

if [[ $? -ne 0 ]]; then
	echo "Error downloading achievements CSV file $URL"
	exit 1
fi

if [[ ! -f $CSV_FILE ]]; then
	echo "CSV file not found"
	exit 1
fi


sed -i '1,4d' $CSV_FILE # Delete headers of achievements.csv

if [[ -f $DATABASE_FILE ]]; then
	rm $DATABASE_FILE
fi

cat $lifestream_dir/datafiles/achievements_schema.sql | sqlite3 $DATABASE_FILE

echo -e ".mode csv\n.import $CSV_FILE achievements" | sqlite3 $DATABASE_FILE
