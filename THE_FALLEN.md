# The Fallen

Importers that no longer work because the service shut down or the API changed beyond repair.

To retrieve a file from git history: `git show <commit>:the_fallen/<filename>`

| File | Description | Retired at |
|------|-------------|------------|
| `moves.py` | Imported activity and location data from Moves app (shut down 2018) | `8bfc218` |
| `openpaths.py` | Imported GPS location history from OpenPaths (shut down ~2020) | `4418044` |
| `tsw.py` | Imported character chronicle data from The Secret World MMO (shut down 2018) | `def8373` |
| `fitbit_day.py` | Imported daily activity and health data from Fitbit API | `708adb7` |

## Retired features

Capabilities dropped from importers that still exist, where the file itself
survives and only part of what it did is gone.

| Importer | Feature | Retired at |
|----------|---------|------------|
| `historic.py` | Replayed ten-year-old tweets alongside the Tumblr reblogs | `15539f2` |

The historic importer was tumblr-only until `f736698` (2015-06-20), which
added the Twitter half and renamed `histumblr.py` to `historic.py` for it. The
two halves never did the same thing: Tumblr posts were reblogged onto a
separate "on this day" blog, while tweets were re-posted on the original
account's own timeline as a reply to the decade-old tweet
(`api.PostUpdate(title, in_reply_to_status_id=systemid)`). The row selection
matched `type = 'twitter'` as well as `source = 'tumblr'`.

`15539f2` (2024-11-11) removed the branch, the `twitter_historical.oauth`
dance, the `[twitter] accounts` check, and narrowed the query back to
`source = 'tumblr'`.

One fossil is still in `historic.py`: the `@` to 💬 substitution, added by
`47c4a67` to stop a replayed tweet re-notifying everyone mentioned in it ten
years earlier. It now only affects a log line.
