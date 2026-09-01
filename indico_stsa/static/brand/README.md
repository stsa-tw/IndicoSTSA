# STSA marks

Straight from <https://github.com/stsa-tw/Assets>, renamed for what they are:

| here | there | used for |
| --- | --- | --- |
| `logo-white.png` | `logo.png` | reversed out of the ticket's navy field |
| `emblem.png` | `favicon.png` | the ticket footer, in colour |
| `logo-black.png` | `logo_black.png` | spare, for a light background |

These are the association's own marks, so they ship with the association's own
plugin. After replacing one, rebuild the ticket artwork:

```bash
python scripts/build-ticket-artwork.py
```
