@REM Description: This script updates the SaintCoinach.Cmd tool by downloading the latest release from GitHub and extracting it.
@REM Usage: Run this script in a command prompt
@REM Requirements: curl, jq, tar (or any compatible extraction tool)


@REM You will need to update the path to your FFXIV installation if it differs.

@echo off

set SCLocation="G:\Apps\SaintCoinach"
set XIVLocation="C:\Program Files (x86)\Steam\steamapps\common\FINAL FANTASY XIV Online"

if not exist %SCLocation% (
    mkdir %SCLocation%
    echo Created directory %SCLocation%
)

cd /D %SCLocation%


echo Updating SaintCoinach.Cmd...
curl -s https://api.github.com/repos/xivapi/SaintCoinach/releases/latest | jq -r ".assets[] | select(.name? | match(\"SaintCoinach.Cmd.zip\")) | .browser_download_url"

if not exist SaintCoinach.Cmd.zip (
    echo Download failed or file does not exist.
    exit /b 1
)

echo Extracting SaintCoinach.Cmd.zip...
tar -xf SaintCoinach.Cmd.zip

echo Deleting SaintCoinach.History.zip if it exists...
if exist SaintCoinach.History.zip (
  del SaintCoinach.History.zip
  echo Deleted SaintCoinach.History.zip
)

SaintCoinach.Cmd.exe %XIVLocation% ui uihd