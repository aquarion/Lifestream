# Update FFXIV Image Cache instructions

This tool exports FINAL FANTASY XIV achievement icons straight from your game
installation and uploads them to your remote server.

Icon extraction now uses the [`saintcoinach`](https://github.com/aquarion/saintcoinach-py)
Python library, so there is no longer any need to download or run
`SaintCoinach.Cmd.exe`, and no PowerShell/.NET is involved — the whole flow is
Python and runs the same on Linux, macOS and Windows.

## Setup

1. Copy `ffxiv_config.example.ini` to `ffxiv_config.ini` and fill it in:
   - `local.ffxiv_installation` — your FFXIV install (the folder containing
     `game/sqpack`).
   - `local.icon_directory` — where the exported icon cache should live.
   - `local.data_directory` — where the local achievement database is stored.
   - the `[remote]` keys — your upload target.
2. Install dependencies (this also pulls in the `saintcoinach` library and
   Pillow):
   - If you have direnv, the supplied config should just work.
   - Otherwise: `python -m venv .venv` then `source .venv/bin/activate`.
   - `poetry install` (run `pip install poetry` first if needed).

## Run

```bash
poetry run python update_sc_and_update_icons.py
```

This will:

1. Refresh the local achievement database.
2. Export the icons those achievements use (standard + `hr1`) into
   `<icon_directory>/<game_version>/ui/icon/...`.
3. Prune older `<game_version>` icon caches.
4. Upload any new/changed icons to the remote server.

Only the icons referenced by achievements are exported, rather than every UI
icon in the game, so the export is quick.

Useful flags:

- `--verbose` / `--debug` — more logging.
- `--disable-tqdm` — turn off progress bars.
- `--skip-export` — only run the uploader (reuse the existing icon cache).
- `--skip-upload` — only export icons, don't upload.

You can also run the uploader on its own, exactly as before, with
`poetry run python update_achievement_images.py`.
