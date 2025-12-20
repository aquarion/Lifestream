# Update FFXIV Image Cache intructions

This script sends all the achivement icons up to your remote server.

## 1. Update SaintCoinach image cache

### Automatic Version

Copy `update_sc.bat` into your SaintCoinach directory, and run it to update SC and extract the icons. This will require having jq and tar installed, probably via [Chocolatey](https://chocolatey.org/install)

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

## 2. Update the images on the server

- Make sure `ffxiv_config.ini` is updated (use `ffxiv_config.example.ini` as a template)
- Create a new python virtual env:
  - If you have direnv, the supplied config file should just work.
  - Otherwise: `python -M venv .venv` then `source .venv/bin/activate`
  - Install the required python modules: `poetry install`
  - If poetry isn't installed, you may need to run `pip install poetry` first.
- Run `python ./update_achievement_images.py`

### Notes on Windows

This runs a lot quicker under native Windows than it does under WSL at the expense of being more of a faff to set up.

To make the above work, you'll need to first install the [Microsoft Build Tools for Visual Studio](https://visualstudio.microsoft.com/vs/older-downloads/) (It works with 2022). After that poetry should run fine as above, but you may need to install the cffi dependancy manually via `pip install "cffi (==1.17.1)"`