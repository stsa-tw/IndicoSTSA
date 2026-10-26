# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An Indico plugin (`indico-plugin-stsa`, entry point `indico.plugins` → `stsa`) that adds ten
independent, default-off customizations for the Singapore Taiwanese Student Association: e-mail
subject prefixes, a per-registration-form member discount, a members-only gate on group
registration, the Apple/Google wallet badges, an STSA ticket design with Chinese-capable fonts, an
Apple Wallet pass drawn in Xcode's Pass Designer, a one-click payment reminder for everybody who
still owes money, holding a signed-in member's registration e-mail to the address on their
membership, four registration field types (中文姓名, 英文姓名, 就讀科系, 目前身分) that a
signed-in member's account fills in and locks, a JSON endpoint that lists the events a
participant has registered for, and (not a switchable feature, just for administrators) an OpenAPI
document of every endpoint the instance has, drawn with a vendored Scalar.

`README.md` documents *why* almost every design decision was made — read the relevant section before
changing behaviour, because most of the odd-looking code is deliberate and the rejected alternatives
are written down.

## Commands

```bash
pip install -e '.[dev]'          # plugin + pytest/ruff
pytest                           # unit tests (no Indico DB needed)
pytest tests/test_ticket.py -v   # one file
pytest -k discountable_amount    # one test
ruff check .                     # lint (CI runs `ruff check --output-format=github .`)
```

Asset build (needed for any change under `indico_stsa/client/`) — requires an Indico **source**
checkout at the matching version, plus `npm ci` in it, and must run with the Python that Indico and
this plugin are installed into:

```bash
python build-assets.py --indico-source ~/dev/indico [--dev] [--watch]
```

Runtime/maintenance:

```bash
indico stsa install-ticket [--no-default] [--dry-run] [--category-id N]
python scripts/build-ticket-artwork.py                       # regenerate static/ticket/background.png
python scripts/install-apple-badges.py ~/Downloads/Add-to-Apple-Wallet.zip
python scripts/sign-preview-pass.py --certificate … --key …   # build a real signed .pkpass
python scripts/sign-preview-pass.py --certificate c.pem --key k.pem   # sign a real one to open in Wallet
python scripts/update-scalar.py 1.76.0                        # re-vendor Scalar (verifies npm's SHA-512)
python .github/scripts/check_wheel.py dist                   # release gate on wheel contents
```

## Architecture

### Hook-up

[plugin.py](indico_stsa/plugin.py) is the single place every Indico signal, template hook and bundle
injection is wired; each handler is a thin `try/except` wrapper that logs and returns the "as if the
plugin weren't installed" result, then delegates to a feature module. That failure-safety is a
requirement, not defensive noise: a broken setting must never cost somebody a registration
confirmation or a working page.

### Layering

The split is deliberate and worth preserving: **pure modules take no Indico/DB dependency and carry
all the unit tests**, while their DB-touching counterparts are exercised only against a live Indico.

| Pure | DB / Indico |
| --- | --- |
| [discount.py](indico_stsa/discount.py) — *how much* | [pricing.py](indico_stsa/pricing.py) — *whether*, and writing it |
| [emails.py](indico_stsa/emails.py) — subject rewriting | `plugin._intercept_make_email` |
| [group_preview.py](indico_stsa/group_preview.py) — re-quoting the plan picker | `plugin._intercept_submission_data` |
| [wallet.py](indico_stsa/wallet.py) — locale → artwork | [ticket_email.py](indico_stsa/ticket_email.py) |
| [ticket.py](indico_stsa/ticket.py) — the design | [install_ticket.py](indico_stsa/install_ticket.py) |
| [wallet_pass.py](indico_stsa/wallet_pass.py) — the pass's colours, images and fields | `plugin._style_apple_wallet_pass`, `plugin._refine_apple_wallet_ticket` |
| [reminders.py](indico_stsa/reminders.py) — *who owes*, and what the mail says | [payments.py](indico_stsa/payments.py) — *finding* them |
| [email_lock.py](indico_stsa/email_lock.py) — *which* field, and *whether* an address is the member's | `util.email_lock_member` — *whom* the lock applies to |
| [profile.py](indico_stsa/profile.py) — *what* a claim reads as, and the padlock's data | `util.member_profile` — *whose* claims, `handlers.apply_member_profile` — writing them |
| [names.py](indico_stsa/names.py) — what a name is, the form without First/Last name, injecting them | `util.disabled_names` — *whether* they are off, [default_names.py](indico_stsa/default_names.py) — the wrappers of core, `handlers.sync_default_names` — writing them |
| [attendance.py](indico_stsa/attendance.py) — what a registration's *status* is, what the query string meant | [registered_events.py](indico_stsa/registered_events.py) — *finding* them and the payload, [controllers/api.py](indico_stsa/controllers/api.py) — the endpoint |
| [openapi.py](indico_stsa/openapi.py) — the document from plain `Operation`s, [marshmallow_schema.py](indico_stsa/marshmallow_schema.py) — a schema as JSON Schema | [api_docs.py](indico_stsa/api_docs.py) — *finding* the operations in the URL map, [controllers/docs.py](indico_stsa/controllers/docs.py) — the admin-only handlers |

[constants.py](indico_stsa/constants.py) holds every shared name so modules that must not import
each other still agree; [util.py](indico_stsa/util.py) holds lookups, field provisioning and the
bridge to the group plugin.

### The member discount

Stored as a value on a plugin-owned billable registration field
(`ext__stsa_member_discount` — the `ext__` prefix is mandatory for plugin fields) so it renders as a
named invoice line. The field is **locked** via `is_field_data_locked`, which makes core skip it in
`create_registration`/`modify_registration`; that is what lets `pricing.py` be the only writer.
`calculate_price` only receives the stored value, so the amount must be computed and written *before*
core prices anything.

The field is internal, so it is hidden in every place core exposes a form's fields to an organizer:
the form editor (client side, below), and the registrant list's *Customize list* dialog
([reglist.py](indico_stsa/reglist.py)). That dialog walks `regform.sections` straight from
`management/reglist_filter.html` and core offers no hook, so the fix is Flask's own
`before_render_template`, filtering the template's context. **Not** a template customization path:
those replace a core template wholesale, and the group registration plugin needs the same file
changed for the same reason — the second one to register would silently lose.

Membership test: `registration.user is not None and session.user == registration.user` — both halves
are load-bearing (see `util.registration_is_member`). Registrations made from the management area
are trusted instead. Once earned, the discount is only ever added on update, never removed
(`upgrade_only=True`).

### The plan picker's price

The group plugin's picker prices each plan in the browser from one number,
`basePrice` in its field data — the form's standard fee, which knows nothing
about the member discount. `plugin._intercept_submission_data` intercepts
`get_flat_section_submission_data` (core's `@make_interceptable`, same mechanism
as the e-mail subjects) and `group_preview.quote_member_price` writes the fee the
member actually pays; `pricing.preview_base_price` decides whether it lands at
all, by reading `apply_member_discount`'s decision forwards. **The fee is
rewritten, not the plan list** — the join preview fetches its plan over AJAX and
prices it against the same fee, so only the fee reaches both.

The picker has two fees and only `payerBasePrice` is ours to write: `basePrice`
is what the group plugin works a plan's own rate out from when its *applies to*
is the fee, so moving it would compound the two discounts, which the server
never does. `payerBasePrice` needs group registration **0.2.4**; older versions
have only `basePrice`, and `quote_member_price` falls back to it for a quote
that is high rather than absent.

### The membership's e-mail address

While a member is signed in, the registration form's *E-mail* field is held to an address on their
account. The padlock is drawn by writing `lockedReason` into the flat submission data (the same
interception as the group plan picker's price) and **not** through `is_field_data_locked`: core
*skips* a locked field when a registration is created, and `Registration.email` is not nullable, so
that signal would turn every registration into an integrity error. Core's own `data-lock-email` is
not available either — the template always renders it, and a duplicate attribute is not read.

The rule is enforced by `before_check_registration_email`, which core runs both on the form's live
check and on the submitted registration; it answers with core's own `email-other-user` conflict
because the form renders that as "This email address is not associated with your Indico account"
and renders an unknown one as something wrong and alarming. Every address on the account is
accepted (`get_user_by_email` matches secondary ones, so those registrations are already linked to
the right membership). Organizers, somebody else's registration opened from its link, and
invitations are all carve-outs — see `util.email_lock_member`. The draft skips the e-mail field
while the lock applies, or it would restore an address the server refuses into a field nobody can
correct.

### Membership details on the form

Four field types (`ext__stsa_chinese_name`, `_english_name`, `_major`, `_year_of_study`, all in
`constants.PROFILE_FIELDS` with the claim each is filled from) that a signed-in member's account
fills in and locks. Plain string fields as far as core is concerned — all the behaviour is around
them. The claims reach `Identity.data` at login, and **Indico drops them by default**: every
identity provider builds its data through `identity_info_keys`, which Indico sets to the user fields
it syncs, so `chinese_name` never arrives. `plugin._keep_profile_claims` wraps each provider's
`get_identity_from_auth` at `app_created` and `profile.keep_profile_claims` copies the four across
from `AuthInfo.data`, gated on the admin switch at login time. Tests that write `Identity.data`
directly **bypass this** — 0.4.0 shipped broken because the e2e did; only a real OIDC round trip
(see the harness memory) proves it. With the `openid` scope Indico reads the **ID token**, not the
userinfo endpoint (`use_id_token`), so claims that authentik leaves out of it never arrive at all;
`profile.no_claims_sent` makes the login wrapper log the claim *names* that did arrive, never values.
`util.member_profile` reads the identity in `session['login_identity']` (and only if it is the
user's own), and asks `email_lock_member` whose form it is, so organizers, somebody else's
registration and invitations are the same carve-outs as the e-mail lock.

Same padlock mechanism as the e-mail (`lockedReason` in the flat submission data, **not**
`is_field_data_locked`, which would make core skip the field where there is no claim) plus
`autofillValue`, which `ProfileInput.jsx` writes into the form. The server is the authority:
`handlers.apply_member_profile` runs on `registration_created`/`_updated` and overwrites the stored
value — but only on a row core already kept, so a field hidden by a condition or purged is not
revived. Locking is per field: a claim that is absent or blank leaves its field open.

All four types **must** be named in `client/js/index.jsx`, or core's form editor crashes on them;
`tests/test_client_registry.py` holds the two lists together. The draft skips `config.lockedFields`
so a value typed while signed out cannot be restored over the account's, and skips blank values so an
empty first name cannot be restored over the one core filled in from it.

The new field's title is prefilled by `PrefilledTitle.jsx`, **not** `settingsFormInitialData`: core's
"Add new field" dialog keeps *Submit* disabled until the form is dirty, so an initial value that is
already valid left the button dead until the organizer changed something. It writes the title one
tick after mount because the dialog's content and its button mount in the same commit and
`useFormState` drops the first notification — a change made in between never reaches the button.

### First and Last name, switched off

Core will not let First/Last name be disabled: `PersonalDataType.is_required`, the `pd_field_enabled`
check constraint, a non-null `Registration.first_name`, participant-list columns that look them up as
active fields. So they are **never** disabled — the switch is `first_name_disabled`/`last_name_disabled`
on `STSASettings`, and `default_names.py` makes the rest behave like it. Wrapped in core, once, in
`plugin.init`: `RegistrationFormPersonalDataField.view_data` (drops `fieldIsRequired`, reports
`isEnabled: False` — that is what gives the editor its *Disable* button and the greyed look) and
`RHRegistrationFormToggleFieldState._process` (which refuses required fields). Both fall through to
core for anything that is not First/Last name on a form with the English/Chinese name field
(`NAME_SOURCES`: English → first, Chinese → last, so the full name reads English first).

`get_flat_section_submission_data` is intercepted to drop the two items and mark the supplying field
required; the schema's `schema_pre_load` signal (sender is the dynamic `RegistrationSchemaBase`
subclass, so the form is found from `request.view_args['reg_form_id']`) overwrites
`first_name`/`last_name` from the submitted names *before* core validates — core parses twice, so
`names.inject_names` is idempotent, and an **absent** source is skipped (a modification that did not
touch it) while a **blank** one raises a `ValidationError` on the visible field.
`handlers.sync_default_names` runs after `apply_member_profile` and writes the columns *and* the answer
rows. `util.disabled_names` rechecks the source on every call, and the field-changed/-toggled/-deleted
receivers clear the switch when the source goes (core announces a delete *before* it happens).
Position: a switched-off field is moved after the enabled ones, because the editor draws it with the
disabled fields and counts drag positions without it.

If you touch this, know what it was tested against: the editor toggle, a member's registration through a
real OIDC login, management *Add registrant* (blank English name refused on `field_13`), a management
modification that sent only the Chinese name, the switch released by disabling the English name, and a
*show if* on Last Name removed again on save. None of it has unit coverage beyond `names.py`.

### The registered-events API

`GET /api/stsa/registered-events` ([controllers/api.py](indico_stsa/controllers/api.py)): the signed-in
caller's own registrations, filtered by `from`/`to` (the event overlaps the window; a bare date is the
whole day, so `to` includes it) and `status` (`attendance.STATUSES`: upcoming, ongoing, checked_in,
no_show, pending, withdrawn, rejected). It is a `json_errors` RH under `@oauth_scope('read:user')` —
**not** the default scope, which core demands `read:everything` for and reserves for non-API pages — and
there is no way to name another user, so nothing here is for an organizer's token to be used on.

Which forms are in it is `STSASettings.include_in_events_api`, per **registration form**, default off,
and the query *joins* the settings row, so a form nobody configured (or an install whose tables were
never upgraded) lists nothing rather than everything. Status and window are applied in **Python**, to
the one participant's rows, through `attendance.py` — deliberately not repeated in SQL, so what a
registration is listed as and what it is filtered by cannot disagree. `unpaid` is not a status (it holds
a place, so it is `upcoming`/`no_show`; the payload carries `registration.state`), `pending` is (the place
is not theirs yet), and `withdrawn`/`rejected` are listed only when asked for.

The blueprint has **no `url_prefix`** for this reason: the endpoint is not about one event, and a plugin
gets one blueprint (two would both register as `plugin_stsa`). Every management rule spells out
`/event/<int:event_id>` itself; the URLs are unchanged.

Tested live against the harness: the status/window matrix, the three auth outcomes (no credentials 403,
bad token 401, token without the scope 403), the settings form, and a database without the newest column.

### The API reference

Administration → Integration → *API reference* (`/admin/stsa/api-docs/`): Scalar drawing an OpenAPI 3.1
document generated from the running instance's URL map. **Every handler in
[controllers/docs.py](indico_stsa/controllers/docs.py) is `RHAdminBase`** — the page, `openapi.json`, and
`scalar.js` — and `tests/test_api_docs_guard.py` fails on any new `RH` in that module that is not. Scalar's
script is served by a handler rather than from `static/` on purpose: `/static/plugins/stsa/` serves
everything under `static/` to anybody, so the bundle lives in `indico_stsa/vendor/scalar/` and
`check_wheel.py` refuses a wheel that has a `standalone.js` under `static/`.

Finding the endpoints is a heuristic in `api_docs.is_api` (an `/api/` URL, or a handler with its own
`@oauth_scope`; the `api` blueprint's key-management *pages* are excluded by name). The handler class is
recovered from `IndicoBlueprint.add_url_rule`'s `make_view_func` closure (variable `obj`), and a handler's
argument schemas from the **closures of webargs' wrappers** (`argmap`, `location`, then the factory's
`schema_cls`/`schema_kwargs`). All of that is looked up *by name* and every failure degrades to "nothing
known about that argument", never to a failed document — so a new Indico that builds its wrappers
differently loses detail silently; the live check below is what notices. A handler that reads
`request.args` by hand declares what it takes with `_OPENAPI_PARAMETERS` / `_OPENAPI_RESPONSE`
(`RHSTSARegisteredEvents` does). Responses are otherwise "a successful response": Indico writes nothing
down.

`openapi.py` and `marshmallow_schema.py` are pure and unit-tested; the document of a real instance was
validated with `openapi-spec-validator` (not a dependency — `pip install` it in the harness) and drawn in
Scalar under the strict CSP the page sets (no `unsafe-eval`, `connect-src 'self'`) with an administrator, a
member, a token without the scope, and nobody. Scalar is configured with telemetry, its agent and its web
fonts off; the CSP would stop them anyway. It is **vendored byte for byte** —
`scripts/update-scalar.py <version>` takes `dist/browser/standalone.js` out of the npm tarball after
checking the registry's SHA-512 and records the file's SHA-256 in `scalar.json`; `tests/test_vendor.py`
holds the file to it, and `.gitattributes` marks it `-text` so a line-ending conversion cannot change it.

### Client side

One webpack bundle (`webpack-bundles.json` → `client/js/index.jsx`), injected into
`WPConferenceDisplayBase`, `WPSimpleEventDisplayBase` and `WPManageRegistration` only — `inject_bundle`
matches subclasses, so adding a regform view under one of those bases would run the wallet
enhancement twice.

The member discount field is registered with core's field registry
(`registerPluginObject('stsa', 'regformCustomFields', …)`) so that it can be *hidden*: an
unregistered input type renders as `Unknown input type: …` wherever a manager sees the form. The
component renders only a marker, and `styles/main.scss` hides the whole `.regform-section` that
contains it — the section is the plugin's own, so nothing else is in it.

All server→React data travels as a single `data-stsa` JSON attribute on the regform root, produced by
the `regform-container-attrs` hook and read straight off the DOM in [config.js](indico_stsa/client/js/config.js)
(never via core's redux selectors, which are not plugin API). React pieces register through
`registerPluginComponent`. The draft that survives the login round trip lives in `sessionStorage`
([draft.js](indico_stsa/client/js/draft.js), [useDraft.js](indico_stsa/client/js/useDraft.js)); file
uploads and captcha answers are deliberately not restored.

[wallet.js](indico_stsa/client/js/wallet.js) rewrites finished server-rendered markup rather than
forking core templates, and finds the wallet links by **URL pattern**. Artwork URLs reach it through
`<meta name="stsa-wallet-*">` tags in the document head — not `get_vars_js`, which is cached per
Indico version and would make the admin switch appear dead.

### Ticket rendering

Two layers sharing one coordinate system (designer pixels, 50px = 1cm): furniture (bands, rules,
perforation) is a prebuilt background PNG from `scripts/build-ticket-artwork.py`, because Indico's
designer canvas has no line or rectangle primitive; text and QR are items in `ticket.py`. **Move a
rule in the script and you must move the text in `ticket.py`.**

[fonts.py](indico_stsa/fonts.py) re-backs Indico's `serif`/`sans-serif`/`courier` families with the
Noto CJK faces Indico already ships. Nothing may request bold — these are variable fonts and
ReportLab renders the default instance. [emoji.py](indico_stsa/emoji.py) handles lines whose text
needs two faces by composing them run-by-run into an image (a `Paragraph` is one face only), falling
back to dropping the characters.

`install-ticket` is a CLI command and never runs automatically: the template is found by title and
updated in place so events keep pointing at it, and re-running is how a design upgrade is applied.

### Payment reminders

A **Remind unpaid (N)** button in the registrant list toolbar, added through core's
`registration-status-action-button` template hook — *not* `registrant_list_action_menu`: both the
*Actions* dropdown and every entry in it carry the `disabled` class that only
`js-requires-selected-row` removes, so an action that ignores the selection is unreachable there.

`RHSTSAPaymentReminders` subclasses core's `RHRegistrationEmailRegistrants` and replaces only
`_process_args`, so the recipients are **found, not submitted** — on the send as well as on the open,
which is what drops somebody who paid while the dialog sat open and what stops the posted
`registration_id` list being trusted. Everything else (placeholders, event locale, sender addresses,
the log entry) is core's. `attach_ticket` is deleted from the form: nobody on the list has paid.

Unpaid means all three of `state == unpaid`, `not is_paid` and `price > 0` — the last two decided in
Python because both are computed properties (see `reminders.needs_reminder` for why each matters;
the `is_paid`-but-`unpaid` case is a *pending* bank transfer). `payments.find_unpaid` eager-loads
`data → field_data → field` and `transaction` or each is a query per registrant.

The preview needs its own endpoint: core's `#preview-email` handler quotes the mail against
`getSelectedRows()[0]`, and nothing is selected here, so `RHSTSAPaymentReminderPreview` picks the
first unpaid registration instead. The dialog template is a copy of core's `email.html` because that
one builds the preview URL from the relative endpoint `.email_registrants_preview`, which resolves
against *this plugin's* blueprint and raises `BuildError`.

`payments.OutstandingAmountPlaceholder` adds `{amount}` to the `registration-email` context, which is
instance-wide — hence the `payment_reminders` admin switch, since a name collision would make
`named_objects_from_signal` raise on every registration e-mail. Both endpoints re-check that switch
and `event.has_feature('payment')`, so switching it off actually turns the feature off.

### Group registration plugin (optional companion)

Never imported at module level — presence is checked via `plugin_engine.get_plugin('group_registration')`,
and its answers are read through field lookups. Both plugins write a negative line item, so the
member discount excludes **both** discount fields from its basis (`pricing.DISCOUNT_FIELDS`) and then
calls `util.reprice_group_of` — the dependency runs one way and cannot loop. The gate in
[handlers.py](indico_stsa/handlers.py) reads the *submitted* answer, not the stored one, so it is
independent of signal-handler ordering.

## Conventions and gotchas

- Every read of the plugin's own table goes through `util.tables_exist()`, which asks the inspector
  rather than letting the query fail (a failed statement aborts the whole transaction). An install
  where `indico db --plugin stsa upgrade` was never run has to degrade to "nothing configured" --
  it used to 500 the participant's registration form, not just the management pages. It also checks
  for the newest migration's column (`util.NEWEST_COLUMN`): a table that exists but predates an
  update fails every query the same way. **Move that constant whenever a migration adds a column.**
- Ruff config in [ruff.toml](ruff.toml) mirrors Indico core: single quotes, 120 columns, **isort is
  deliberately off** — match core's grid-style import wrapping by hand.
- All models must live in the `plugin_stsa` schema ([models/__init__.py](indico_stsa/models/__init__.py));
  Indico refuses a plugin that adds one elsewhere. Schema changes need an Alembic revision under
  `indico_stsa/migrations/`, applied with `indico db --plugin stsa upgrade`.
- `.gitattributes` forces LF everywhere; a CRLF round trip on Windows changes every content-hashed
  bundle name.
- **Apple's wallet artwork must never be committed or packaged.** It is gitignored, excluded in
  `pyproject.toml` for both sdist and wheel, and blocked by `tests/test_wallet.py` plus
  `check_wheel.py`. Google's is redistributable and ships.
- `static/dist/` is gitignored but *must* be in the wheel — hence `artifacts` in `pyproject.toml`;
  without it Indico raises "Assets for plugin stsa have not been built" on every registration page.
- pytest runs with `-p no:indico`: Indico's own pytest plugin pulls in a Docker-backed database
  fixture stack the unit tests don't use. Anything touching the DB therefore has **no** unit
  coverage; verify it against a real Indico instance (Indico does not run on Windows). CI compensates
  only by importing every module.
- Releases: bump `__version__` in [__init__.py](indico_stsa/__init__.py); the publish workflow refuses
  a tag that doesn't match it, and PyPI uploads deliberately have no `skip-existing`.
