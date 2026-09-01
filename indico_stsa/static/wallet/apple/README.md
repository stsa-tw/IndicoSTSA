# Apple badge artwork goes here

This directory ships empty, and that is deliberate.

Apple's **Add to Apple Wallet** badge is not ours to hand out. The Wallet
Marketing Artwork License Agreement grants

> a limited, non-exclusive, **non-transferable**, royalty-free, worldwide
> license to use the "Add to Apple Wallet" badge … **only in connection with
> Your passes** … and only while You are a member of the Apple Developer
> Program.

A licence that is non-transferable and tied to *your own* passes cannot travel
inside a public package to whoever installs it next. So every operator gets
their own copy, under their own agreement — which is a formality, since an
Indico that issues Apple passes at all already has an Apple Developer account
and a Pass Type ID.

Until the artwork is here, the plugin leaves Apple's link as the button Indico
shipped. It never substitutes anything, because Apple's guidelines say in as
many words not to make your own badge.

## Installing it

1. Sign in at <https://developer.apple.com/wallet/add-to-apple-wallet-guidelines/>,
   use **Download badge files**, and accept the agreement.
2. Run the installer against the zip you got:

   ```bash
   python scripts/install-apple-badges.py ~/Downloads/Add-to-Apple-Wallet.zip
   ```

   It copies the RGB SVGs in under Apple's own market codes and rasterizes a
   PNG of each for e-mail, since Apple ships no PNG and Gmail and Outlook do not
   render SVG. Proportions and colours are untouched.

3. Restart Indico. The badge appears on the next page load, and the
   "Add to Wallet" dropdown disappears once both badges are in place.

Which market code is used for which language is `APPLE_LOCALES` in
`indico_stsa/wallet.py`.
