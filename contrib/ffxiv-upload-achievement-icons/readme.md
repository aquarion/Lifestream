# Update FFXIV Image Cache intructions

This script sends all the achivement icons up to your remote server.

## 1. Update SaintCoinach image cache

### Automatic Version

Copy `update_sc.bat` into your SaintCoinach directory, and run it to update SC and extract the icons.

### Manual Version

Go to Saint Coinach in windows, update the application settings `SaintCoinach.Cmd.dll.config` to set the data path:

````xml

    <SaintCoinach.Cmd.Properties.Settings>
      <setting name="DataPath" serializeAs="String">
        <value>D:\Steam\steamapps\common\FINAL FANTASY XIV Online</value>
      </setting>
    </SaintCoinach.Cmd.Properties.Settings>```
````

Or launch it with the directory as an argument:

`.\SaintCoinach.Cmd.exe "D:\Steam\steamapps\common\FINAL FANTASY XIV Online"`

Then export the UI elements with `ui` and `uihd`

## 2. Update the Achivements cache

Run the script to update the database of achivements:

`./ffxiv_create_achivements_db.sh`

## 3. Update the images on the server

- Make sure `ffxiv_config.ini` is updated (use `ffxiv_config.example.ini` as a template)
- Create a new python virtual env:
  - If you have direnv, the supplied config file should just work.
  - Otherwise: `python -M venv .venv` then `source .venv/bin/activate`
  - Install the required python modules: `pip install -r requirements.pip`
- Run `python ./update_achievement_images.py`

# Speed

The script is very slow when running under WSL2 and SC is on a Windows drive. One day I should make it be able to run natively under python in Windows. Today is not that day.