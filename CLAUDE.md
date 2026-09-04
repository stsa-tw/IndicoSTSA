# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An Indico plugin (`indico-plugin-stsa`, entry point `indico.plugins` → `stsa`) that adds five
independent, default-off customizations for the Singapore Taiwanese Student Association: e-mail
subject prefixes, a per-registration-form member discount, a members-only gate on group
registration, the Apple/Google wallet badges, and an STSA ticket design with Chinese-capable fonts.

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
  it used to 500 the participant's registration form, not just the management pages.
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
