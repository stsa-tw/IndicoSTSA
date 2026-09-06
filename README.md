# Indico STSA plugin

Customizations for the Singapore Taiwanese Student Association.

Seven things, each independently switchable:

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
6. **Payment reminders.** One button in the registrant list writes to everybody
   whose registration fee is still outstanding, each mail naming what that
   person owes.
7. **The membership's e-mail address.** A member who is signed in registers
   under the address on their membership, so their registrations can always be
   matched back to them.

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

Missing that last step does not take anything down. Without its tables the
plugin reads as *nothing configured*: the member discount and the group gate
are off, registration forms and e-mails behave exactly as they would with the
plugin uninstalled, and the STSA pages in the management area say what is
missing and print the command above instead of failing. The same line goes to
the server log once per process.

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

### The invoice line, and why organizers never see it

The discount is stored as a value on a billable registration field the plugin
provisions for itself — `ext__stsa_member_discount`, in a manager-only section
called *Member discount (internal)*. That is what makes it a named **Member
discount** line with a rate next to it rather than Indico's unlabelled "Price
adjustment", and the plugin is its only writer: the field is locked, so core
skips it when a registration is created or modified.

None of it is an organizer's business, so the field and its section are hidden
wherever a manager sees the form — the form editor and the management
registration form alike. The field is registered with core's React field
registry precisely so that it *can* be hidden: an input type no plugin has
registered renders as `Unknown input type: ext__stsa_member_discount`, which is
how organizers used to meet it. It is kept out of the **Add field** dropdown for
the same reason — the plugin provisions the field itself, and a second copy
would be a second invoice line that nothing ever writes to.

The registration list's **Customize list** dialog offers every field on the form
as a column, this one included, so it is filtered out of that dialog too. If
somebody had already switched the column on, opening the dialog once and
applying it puts that right.

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

The link a registration has to a membership account is the whole test, so it is
not left to whatever somebody types: while a member is signed in, the e-mail
field is held to the address on their membership — see
[The membership's e-mail address](#7-the-memberships-e-mail-address).

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

### Emoji

An event called 秋季迎新晚會 🎉 printed a crossed box where the emoji should be:
no CJK font has emoji glyphs, and ReportLab draws `.notdef` for a codepoint the
font is missing. There is no fixing that within the text path — a `Paragraph` is
drawn in exactly one face, and Indico strips inline markup out of the text before
it gets there, so a second font cannot be asked for mid-line.

So a line that needs two fonts is not drawn as text. It is composed run by run,
each run in the font that has the glyphs, and handed back as an image — which
the badge renderer already knows how to place. Everything else stays on the
vector text path; only the lines that would have been boxes change. The image is
composed at 4× and the box is sized to what came out, so it stays crisp and is
never stretched.

The emoji are **monochrome** (Noto Emoji, OFL, shipped with the plugin). That is
deliberate as well as convenient: tickets are usually printed, often in black
and white, and colour emoji are bitmap fonts that ReportLab cannot embed at all.

If the font is ever missing, or composing fails, the characters are dropped
instead. A title reading 秋季迎新晚會 is a small loss; one reading 秋季迎新晚會 ⊠
looks broken.

## 6. Payment reminders

The registrant list gets a **Remind unpaid (3)** button, next to *Moderation*
and *Check-in control*. It writes to everybody on that registration form whose
fee is still outstanding, in one click, without anybody having to filter the
list and tick four hundred boxes first.

The count is in the label rather than only in the dialog, so the button says
what it is about to do before it is pressed — and it is not drawn at all when
nobody owes anything, when the event takes no payments, or when the viewer only
has moderation or check-in rights.

### Who counts as unpaid

Three things have to be true, and each one keeps somebody out of the list who
would otherwise be chased for nothing:

* the registration is in Indico's **Awaiting payment** state. That is the only
  state that means a fee is outstanding: *complete* has either paid or was
  never asked to, and *pending*, *rejected* and *withdrawn* are not waiting on
  money.
* **no payment has been made.** This is not the same as the state. A
  transaction that is still `pending` — a bank transfer nobody has confirmed
  yet — counts as paid while deliberately leaving the registration *Awaiting
  payment*. Somebody who has already sent the money must not be chased for it.
* **the fee is above zero.** Removing the fee from registrations that had not
  paid it (*Update Registration Fee* → *Remove fee*) stops Indico asking for the
  money without moving the state, so the price is the only thing left that says
  there is nothing to pay.

The first is a filter on the query; the other two are decided in Python,
because Indico computes both — the price from the registration's billable
answers, the payment from its latest transaction — so neither can be asked of
the database. Both are eager-loaded, or reading them would be two more queries
per registrant.

### The dialog

The button opens core's own e-mail dialog, prefilled: a subject and a body an
organizer can rewrite, the recipient list, the sender addresses they are
allowed to send as, and a preview. It is a subclass of core's *E-mail* action
rather than a new mail sender, so placeholders, the event locale and the event
log entry all behave exactly as they do everywhere else.

The one addition is **`{amount}`**, which renders what that registrant still
owes. The body is one string sent to everybody, so the figure can only reach
the mail as a placeholder — core replaces it per recipient. It is offered to
every registration e-mail, core's own *E-mail* dialog included, because
placeholders are registered per context for the whole instance; that is also
why the feature has an admin switch, since two plugins claiming `amount` would
break *every* registration e-mail rather than only the ones using it.

**Attach ticket** is removed from the dialog. Nobody on this list has paid, so
there is no ticket to attach, and the switch would offer a choice whose only
outcomes are "nothing" and "a warning explaining why it was nothing".

### What is not trusted

The recipients are found, never read off the request — on the send as well as
on the open. So the mail goes to whoever still owes money at the moment **Send**
is pressed, somebody who paid while the dialog sat open is dropped, and the
endpoint cannot be talked into mailing somebody who was never on the list. Both
endpoints check the admin switch and the event's payment feature again for the
same reason: switched off is off, not merely hidden.

### Why not the Actions menu

That is where the rest of the bulk actions live, and core even has a signal for
adding to it (`registrant_list_action_menu`). It does not work for this. Both
the *Actions* dropdown itself and every entry inside it are rendered with the
`disabled` class, which only `js-requires-selected-row` ever takes off again —
so an action that deliberately ignores the selection cannot be reached there at
all. The button goes through `registration-status-action-button` instead, which
is core's own hook for an extra button in that toolbar and which nothing in
core uses, so there is no ordering to negotiate with anybody.

## 7. The membership's e-mail address

On the plugin's admin page, on by default.

Somebody who is signed in finds the registration form's **E-mail** field filled
in from their account, as Indico has always filled it in — and now with a
padlock next to it, saying *Your STSA membership is registered under this
address*. They register under the address on their membership, and the
association can match every registration back to the member who made it. It is
also what keeps the member discount honest: the discount is decided from the
link between a registration and an account, and that link is made from this
field.

Any address **on the account** is accepted, not only the first one. Indico looks
a registration's user up with `get_user_by_email`, which matches secondary
addresses too, so a member who registered under one of theirs is already linked
to the right membership; refusing it would leave them with a registration they
could no longer edit, because the address it already holds is one the form would
no longer take.

Three cases are deliberately left alone:

- **Organizers.** Adding a registration from the management area means typing
  *that participant's* address, so nothing there is locked or checked.
- **Somebody else's registration.** A registration is editable from the link in
  its confirmation e-mail, so the person in front of it need not be the person
  it belongs to. The lock applies only when the registration is the signed-in
  member's own — a member who opens somebody else's link must not stamp their
  own address onto it.
- **Invitations.** The address on an invitation is the organizer's choice, and
  core writes *that* address into the registration whatever was submitted. A
  lock there could only refuse a registration Indico was about to make
  correctly.

### The padlock is not `is_field_data_locked`

That signal is the obvious way to lock a field, and it is what the member
discount field uses — but it means far more than "the participant may not edit
this". Core **skips** a locked field when a registration is created or
modified, leaving its data empty; that is exactly why the discount field can
have this plugin as its only writer. Doing the same to the e-mail field would be
fatal: `Registration.email` is not nullable and is written from that same loop,
so every registration would end in an integrity error long before any handler of
ours could put the address back.

So the padlock is drawn by writing `lockedReason` into the flat submission data
the form is rendered from — the same key core's own `get_locked_reason` fills in
there, so the participant gets core's disabled input and core's padlock with our
wording under it, and none of core's write-side behaviour changes. Core's own
`data-lock-email`, which is how an invitation locks the field, is not available:
the template always renders it, and a second copy of an attribute is not read.

### What actually enforces it

A disabled input is a courtesy, not a rule. The rule is
`before_check_registration_email`, which core asks of every address before it is
used — both when the form checks one as it is typed and when a registration is
submitted, on a new registration and on a modification alike. So a hand-built
POST meets it too, and the answer is core's own `email-other-user` conflict,
which the registration form already renders as *This email address is not
associated with your Indico account*. Answering with a name of our own would
leave the form falling through to a sentence about the account the registration
will not be linked to, which is both alarming and wrong.

The draft that carries answers across the trip to the login page leaves the
e-mail field out once the lock applies. Restoring the address somebody typed
while signed out would put a value the server refuses into the one field they
can no longer correct — and core has already filled it in from the account they
have just signed in with, which is the address they are registering under
anyway.

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

### The price the plan picker quotes

The group plugin's plan picker puts a price against every plan — *Pair, 2
members, 90.00 SGD each* — and shows the same kind of number again when somebody
pastes a code to preview the group they are joining. Both are worked out in the
browser from one number the server hands it: the form's standard registration
fee. The member discount was not in that number, so a signed-in member was
quoted the full price and then charged less than they had been shown.

So the fee itself is re-quoted. `get_flat_section_submission_data` builds the
field data the whole registration form is rendered from and is decorated with
`@make_interceptable`, which is Indico's own invitation for a plugin to step in;
the plugin calls it, and where the discount is going to land it writes the fee
that member actually pays. Changing the fee rather than the plan list is what
fixes both quotes at once — the join preview looks the group's plan up over
AJAX, so a rewritten plan list would never reach it — and it keeps this side
from having an opinion about what a group plan is worth, which is the group
plugin's business.

The picker carries **two** fees for exactly this, and only one of them is ours:
`payerBasePrice`, what the person in front of it pays before a group plan, is
written; `basePrice`, the standard fee, is left alone. That distinction is the
whole of the arithmetic. The group plugin works a plan's own rate out from
whichever of the two its *Discount applies to* setting names, exactly as it does
on the server — so a percentage plan set against the fee does not start
compounding with the member discount just because the picker is quoting a
discounted price. Group registration **0.2.4** is where `payerBasePrice` starts
to exist; against an older one the standard fee is written instead, and the
quote carries the discount but comes out high by the plan's percentage of it.

Whether the discount is going to land is the same decision `apply_member_discount`
makes, read forwards: a registration being edited answers for itself, and a new
one answers for whoever is filling it in, where being signed in is exactly what
the notice above the form already promises is enough. In the management area the
fee belongs to somebody who is not in the room, so the standard fee is quoted.

What no quote can include is the paid options nobody has chosen yet, so a member
who then adds one pays a little more than the number the picker showed. That is
the picker's own long-standing approximation rather than anything to do with the
discount, and the option's price is in front of whoever is choosing it.

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
