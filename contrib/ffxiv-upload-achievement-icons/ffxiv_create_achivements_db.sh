#!/bin/bash

datadir="./data"
mkdir -p $datadir

SQL_FILE=./etc/achievements_schema.sql

CSV_FILE=$datadir/ffxiv_achievements.csv
DATABASE_FILE=$datadir/ffxiv_achievements.db

if [[ ! -f $SQL_FILE ]]; then
	echo "SQL file not found: $SQL_FILE"
	exit 1
fi
if ! hash -r sqlite3 2>/dev/null; then
	echo "sqlite3 not found, please install it"
	exit 1
fi
if ! hash -r curl 2>/dev/null; then
	echo "curl not found, please install it"
	exit 1
fi
if hash -r gsed 2>/dev/null; then
	SED="gsed"
	exit 1
else
	SED="sed"
fi
if ! hash -r $SED 2>/dev/null; then
	echo "sed/gsed not found, please install it"
	exit 1
fi

echo "Get new achivement CSV"
curl -sL "https://github.com/xivapi/ffxiv-datamining/raw/master/csv/Achievement.csv" >$CSV_FILE

$SED -i '1,4d' $CSV_FILE

if [[ -f $DATABASE_FILE ]]; then
	echo "Remove old database file"
	rm $DATABASE_FILE
fi

echo "Create new database"
cat $SQL_FILE | sqlite3 $DATABASE_FILE

echo "Import achivements into new database"
echo -e ".mode csv\n.import $CSV_FILE achievements" | sqlite3 $DATABASE_FILE
