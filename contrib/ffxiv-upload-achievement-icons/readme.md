# Update FFXIV Image Cache intructions

This script sends all the achivement icons up to your remote server.

## 1. Update SaintCoinach image cache

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

- Make sure `config.ini` is updated (use `config.example.ini` as a template)
- Create a new python virtual env:
  - If you have direnv, the supplied config file should just work.
  - Otherwise: `python -M venv .venv` then `source .venv/bin/activate`
  - Install the required python modules: `pip install -r requirements.pip`
- Run `python ./update_achievement_images.py`
