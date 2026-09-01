# Indico STSA plugin

Customizations for the Singapore Taiwanese Student Association.

Three things, all optional and all off until somebody switches them on:

1. **E-mail subject prefixes.** Every mail Indico sends goes out with STSA's own
   prefix instead of `[Indico]`.
2. **A member discount, per registration form.** Money off for anyone who
   registers while signed in with their STSA membership — with the answers they
   have already typed kept intact across the trip to the login page.
3. **Members-only group registration.** Where the
   [group registration plugin](https://github.com/RobotHanzo/IndicoGroupRegistration)
   is also installed, creating or joining a group can be restricted to
   signed-in members.
4. **The standard wallet buttons.** Indico's "Add to Wallet" dropdown is
   replaced with Apple's and Google's own badges, on the registration page and
   in the e-mail the ticket arrives with — and they work without signing in.
5. **An STSA ticket**, in the association's own colours and marks, with a font
   that can actually draw Chinese.

A **member** is anyone signed in. An STSA membership *is* an account on the
site: there is no membership table and no separate sign-up, so "becoming a
member" is exactly "signing in". Every participant-facing string says "STSA
membership" rather than naming Indico.

## Installing

```bash
pip install indico-plugin-stsa
```

Then add it to `PLUGINS` in `indico.conf`:

```python
PLUGINS = {'stsa'}
```

and create its tables:

```bash
indico db --plugin stsa upgrade
```

Restart Indico (and the Celery worker, if you run one).

Released wheels carry the compiled webpack bundle. Installing straight from a
git checkout does not — see [Building the assets](#building-the-assets).

## 1. E-mail subject prefixes

Configured once, for the whole site, at **Administration → Plugins → STSA**:

| Setting | Default | |
| --- | --- | --- |
| Rewrite e-mail subject prefixes | on | The master switch. |
| Subject prefix | `[STSA 活動]` | What `[Indico]` becomes. Empty strips it. |
| Use the Apple and Google wallet badges | on | See [the wallet buttons](#4-the-wallet-buttons). |

Every outgoing mail is covered: registration confirmations, password resets,
event reminders, abstract notifications, and anything a plugin sends. Mails
that deliberately carry *no* prefix — the room booking ones set the prefix block
to empty — are left exactly as they are, because there is nothing there to
replace. The error-report mail's `[Indico@yourserver]` is replaced whole; the
server name it carries is in the body anyway.

### How

Indico builds every mail through `indico.core.notifications.make_email`, which
is decorated with `@make_interceptable` precisely so that a plugin can step in.
The plugin intercepts it, lets Indico build the mail as usual, and rewrites the
subject afterwards.

The obvious alternative — overriding `emails/base.txt` and `emails/base.html`
through `get_template_customization_paths` — was rejected. It only reaches the
mails that go through those templates and do not override the `subject_prefix`
block themselves, it misses every mail built from a plain `subject=` string, and
the value would be fixed at deploy time rather than configurable.

If the setting cannot be read, or the rewrite raises for any reason, the
original subject is used and the mail still goes out. A misconfigured prefix
must never cost somebody their registration confirmation.

## 2. The member discount

Per registration form, at **Event → Registration → STSA**, or from the
**STSA** box on the registration form's own settings page.

| Setting | |
| --- | --- |
| Enable the member discount | Off by default. |
| Discount | A percentage, or a fixed amount in the form's currency. |
| Discount applies to | The registration fee only, or the whole price including paid options. |
| Sign-in notice | Optional. Replaces the built-in wording of the notice. |

### What the participant sees

Somebody who is **not signed in** gets a notice above the form saying what the
discount is worth and a prominent **Sign in with your STSA membership** button.
Following it takes them through the login page and straight back to the form,
with everything they had already typed still in place.

Somebody who **is signed in** sees nothing extra. The discount appears as a
named *Member discount* line on their invoice, their registration summary and
their confirmation e-mail, with the rate next to it.

### Keeping the answers

The answers go into `sessionStorage` when the page is navigated away from
(`pagehide`, which also covers signing in through the header menu rather than
the plugin's own link) and are read back — once, then deleted — when the form
next loads. A draft older than six hours is ignored: that is an abandoned tab,
not a login round trip.

Two things deliberately do not survive: **file uploads**, because the browser
will not let a `File` be put back, and the **captcha answer**, because the
challenge it belongs to is gone. Both fields are simply left untouched.

### Who counts as a member

A registration earns the discount when it is *the account holder's own*. Both
halves of that matter:

- `registration.user` alone is not enough. Core sets it from the **e-mail
  address**, with `get_user_by_email`, so on its own it would hand the discount
  to anybody who types a member's address into an anonymous registration.
- `session.user` alone is not enough either. It would hand the discount to a
  signed-in organizer registering somebody else.

So the test is `registration.user is not None and session.user == registration.user`.
Registrations created from the management area are trusted instead: an organizer
adding a participant has made that decision deliberately.

Once earned, the discount **sticks**. Modifying a registration only ever adds
the discount, never removes it — a participant may well be editing from the link
in their confirmation e-mail with nobody signed in, and losing a discount over a
changed phone number would be indefensible. Switching the discount off on the
form does remove it, on the next change to each registration.

### Applying it to registrations that already exist

Saving the settings only affects registrations made from then on. The
**Apply to existing registrations** button on the settings page reprices
everything on the form, and is deliberately a button rather than a side effect
of saving: it treats *every* registration linked to a membership account as a
member's, including ones made before the discount existed. Somebody whose price
goes up after they have paid will owe the difference, and Indico has no
partial-payment concept to collect it with.

## 3. Members-only group registration

Needs the group registration plugin. The switch is on the same STSA settings
page, and is hidden when that plugin is not installed — a switch that currently
gates nothing should not be offered.

With it on, a participant who is not signed in finds the group plan picker
inert, with a note underneath saying groups are for STSA members and offering
the same sign-in button. A code arriving from a shared join link
(`?group_code=…`) is cleared rather than acted on.

The server refuses the same choice again when the registration is submitted, and
that is the half that enforces the rule. The check reads the *submitted* answer
rather than the stored one, which is what makes it independent of whether the
group plugin's own signal handler has already run: reading the stored answer
would either block every later edit of a registration that is already in a
group, or let the very thing this is meant to stop straight through, depending
on which plugin's handler happened to run first.

Organizers are never gated. Adding a participant to a group from the management
area is a deliberate act by somebody who is already signed in.

## 4. The wallet buttons

Where an organizer has configured the passes, Indico offers them as an
**Add to Wallet** dropdown — or, if only one wallet is set up, as an ordinary
Indico button. Neither is what people look for, and both vendors' guidelines ask
for their own badge instead. So the plugin swaps them for the real thing, in two
places: on the registration page, and in the e-mail the ticket arrives with.

### The artwork

Both badges are the vendors' **official** artwork; neither is drawn by hand,
because both vendors forbid recreating theirs. But only one of them can ship
here:

| | Ships with the plugin? | Source | Languages |
| --- | --- | --- | --- |
| Google | **yes** | the asset packs published with its [brand guidelines](https://developers.google.com/wallet/generic/resources/brand-guidelines) | 27 |
| Apple | **no — you install it** | the pack behind **Download badge files** on its [badge guidelines](https://developer.apple.com/wallet/add-to-apple-wallet-guidelines/) | 24 |

Apple's Wallet Marketing Artwork License Agreement grants a *non-transferable*
licence to use the badge **only in connection with your own passes**, so this
package has no right to hand it on to whoever installs it next. Each deployment
downloads its own copy — a formality for anyone already issuing Apple passes,
since that needs an Apple Developer account regardless — and installs it with:

```bash
python scripts/install-apple-badges.py ~/Downloads/Add-to-Apple-Wallet.zip
```

Until then the Apple link keeps the button Indico shipped. Nothing is
substituted for it. `indico_stsa/static/wallet/apple/README.md` has the details,
and a test plus a release gate make sure the artwork never ends up in a package
by accident.

Apple ships SVG and EPS but no PNG, and e-mail needs one — Gmail and Outlook do
not render SVG at all — so the installer rasterizes Apple's own SVGs at 3× the
rendered height, leaving proportions and colours untouched.

The badge matching the reader's Indico language is used, falling back to
English. Both are rendered at 48px, Google's stated minimum, with clear space
around them and no hover or press effect — both vendors forbid altering their
artwork, and Apple names dimming and animation specifically.

### On the page

A small script rewrites the finished page: it finds the links pointing at
Indico's two wallet endpoints, puts a badge for each in a row below the action
box, and removes the dropdown once nothing is left in it.

The badge keeps the href core gave the link and adds the registration token the
page was opened with. That is a fix, not a liberty: core links these two
endpoints inconsistently. Where only one wallet is configured it uses the
registrant locator, which carries the token — but in the dropdown, the branch
you get when *both* are configured, it links the registration form with no token
at all. Anyone who registered without an account was bounced to a login page
they have no account for and could not add their pass. The badge grants exactly
the access the page it sits on already grants, and nothing more.

The alternative was forking `registration_summary.html`, a 300-line core
template that changes between Indico releases and would then have to be reviewed
on every upgrade for the sake of two buttons. Working on the DOM also fails
safely: if core moves these endpoints, the links are simply not found and the
participant keeps the buttons Indico shipped.

The badges go in a row of their own rather than into the toolbar. That toolbar
is a single non-wrapping flex row sized for Indico's own 30px buttons, and two
48px badges pushed into it slide out past the edge of the box.

### In the e-mail

The same badges are added to the mail the ticket is attached to — which is where
somebody who has just been sent a ticket is actually looking. They appear on
exactly the mails that carry the ticket and no others: the condition mirrors the
one in Indico's `_notify_registration`, so an organizer who has switched ticket
e-mails off does not start getting pass links instead.

The images are **embedded** rather than linked, because most mail clients block
remote images until the reader asks for them and a blocked button is a button
nobody presses. Indico already sends inline images this way for registration
pictures. The links carry the registration's token, so they work without
signing in.

The mail is already rendered by the time the plugin sees it, so the block is
spliced in just above the card's grey footer. If a future Indico changes that
footer the badges land after the card instead — untidy, but still a working
button.

## 5. The ticket

`indico stsa install-ticket` installs 「門票」, a tear-off stub, and makes it the
default ticket for the root category — so every event uses it unless an
organizer picks something else.

```
 ┌──────────────────────────────────────────┐
 │ ▓▓ STSA wordmark            ADMIT ONE    │  navy field, #2F5478
 ├──────────────────────────────────────────┤
 │ 2026 STSA 秋季迎新晚會 Welcome Night      │  Noto Serif CJK
 │                                          │
 │ 持票人 ATTENDEE                          │
 │ 昱辰 林                                   │  the holder is the hero
 │ 日期時間 WHEN      地點 WHERE             │
 │ - - - - - - - - - - - - - - - - - - - - -│  the tear line
 │ ███████  入場憑證 ENTRY PASS              │
 │ ███████  昱辰 林   NO. 4                  │  the stub names them again
 │ (emblem)          Admits the named holder │
 └══════════════════════════════════════════┘  oxblood rule, #8A2424
```

Re-running is how an upgrade is applied: the template is found by title and
updated in place, so events already pointing at it keep pointing at it. It never
runs by itself — a plugin that rewrote a template on every start would silently
undo an organizer's edits. `--no-default` installs it without taking over, and
`--dry-run` says what would change and rolls back.

Once installed it is an ordinary designer template: organizers can open it and
change it, and their edits survive until somebody re-runs the command.

### Why the design is two layers

Indico's designer canvas positions text and images and nothing else — there is
no line or rectangle primitive. So every band, rule and the perforation arrives
as one background PNG, built by `scripts/build-ticket-artwork.py` from the marks
in `indico_stsa/static/brand/` (taken from
[stsa-tw/Assets](https://github.com/stsa-tw/Assets)). The text and the QR sit on
top. The two halves share a coordinate system: move a rule in the script, move
the text in `indico_stsa/ticket.py`.

The palette is sampled from the emblem itself — `#2F5478` from the merlion half,
`#8A2424` from the bear — rather than picked to look nice next to it.

### Chinese

Indico offers badge fonts that cannot draw Chinese. The Liberation faces have no
CJK glyphs and fall back to empty boxes; the two Kochi faces are Japanese; UMing
is dated. Meanwhile Indico *ships* Noto Sans CJK and Noto Serif CJK and
registers neither.

So the plugin backs Indico's `serif`, `sans-serif` and `courier` families with
those faces. Every template in the instance gets Chinese, not only this one, and
a badge already set in `sans-serif` keeps working — it just stops producing tofu
the moment a name is in Chinese. It costs nothing to ship, since the fonts are
already there. Switch it off at **Administration → Plugins → STSA** if you would
rather keep Liberation's metrics.

Nothing on the ticket asks for bold. These are variable fonts and ReportLab
renders their default instance, so a bold request would come out at regular
weight; hierarchy is built from size, colour and the serif/sans contrast, which
do arrive.

## Working with the group registration plugin

Both plugins put a negative line item on the registration, and both compute it
from "everything billable except my own line". Left alone, each would be
calculated from the other and every recomputation would move both.

So the member discount is calculated from the registration fee and the paid
options **only** — both discount lines are excluded from its basis. The group
discount is then free to stack on top of it, and whenever the member discount
changes, the plugin asks the group plugin to recompute the group's line so it is
never one registration out of date. The dependency runs one way, so it cannot
loop.

Neither plugin can push a registration below zero: each clamps its own line to
the amount it applies to, and Indico clamps the total at zero regardless.

The plugin works perfectly well without the group registration plugin; the group
switch simply disappears.

## Building the assets

Released wheels already carry the compiled bundle. From a git checkout you need
an Indico *source* tree at the version the plugin runs against:

```bash
git clone --branch v3.3.13 https://github.com/indico/indico ~/dev/indico
(cd ~/dev/indico && npm ci)

/opt/indico/.venv/bin/python build-assets.py --indico-source ~/dev/indico
```

Run it with the Python that Indico and this plugin are installed into: the build
resolves the plugin's own URL rules by importing it. `--dev` and `--watch` are
passed through.

## Tests

```bash
pip install -e '.[dev]'
pytest
```

The unit tests cover the parts that hold the arithmetic and the string handling
and need neither Indico nor a database. Everything that talks to the database is
exercised against a real Indico instance.

## Licence

MIT.
