# Wallet badge artwork

Both vendors require their own artwork to be used and forbid recreating it, so
this directory holds their files. The plugin shows a badge only where it has
one; a vendor with no artwork keeps the button Indico shipped.

Two formats, for two places: **SVG** on the web, and **PNG** in e-mail, because
Gmail and Outlook do not render SVG at all.

Files are named by each vendor's own locale code, mapped from Indico's locales
by `GOOGLE_LOCALES` and `APPLE_LOCALES` in `indico_stsa/wallet.py`. A language
that is not in the map falls back to English.

## `google/`

Google's official **Add to Google Wallet** buttons, from the asset packs
published with its
[brand guidelines](https://developers.google.com/wallet/generic/resources/brand-guidelines)
— `add-to-wallet-svg.zip` and `add-to-wallet-png.zip`. Copy
`<code>_add_to_google_wallet_wallet-button.<ext>` in here as `<code>.<ext>`.

## `apple/`

**Empty, and stays empty in the package.** Apple's Wallet Marketing Artwork
License Agreement is *non-transferable* and covers only the licensee's own
passes, so this package has no right to hand the badge on to whoever installs it
next. Each operator downloads their own copy and runs

```bash
python scripts/install-apple-badges.py ~/Downloads/Add-to-Apple-Wallet.zip
```

See `apple/README.md`. Until then the plugin leaves Apple's link as the button
Indico shipped, and never substitutes artwork of its own.

## Sizing

The plugin renders both at 48px high, which is Google's stated minimum for its
button and comfortably above Apple's for its badge, and leaves clear space
around them. Do not scale the files themselves.
