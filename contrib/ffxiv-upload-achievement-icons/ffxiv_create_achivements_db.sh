#!/bin/bash


datadir="./data"
mkdir -p $datadir

SQL_FILE=./etc/achievements_schema.sql

CSV_FILE=$datadir/ffxiv_achievements.csv
DATABASE_FILE=$datadir/ffxiv_achievements.db

echo "Get new achivement CSV"
curl -sL "https://github.com/xivapi/ffxiv-datamining/raw/master/csv/Achievement.csv" > $CSV_FILE

sed -i '1,4d' $CSV_FILE

if [[ -f $DATABASE_FILE ]]; then
    echo "Remove old database file"
    rm $DATABASE_FILE
fi

echo "Create new database"
cat $SQL_FILE | sqlite3 $DATABASE_FILE

echo "Import achivements into new database"
echo -e ".mode csv\n.import $CSV_FILE achievements" | sqlite3 $DATABASE_FILE 

