"""Putting the wallet badges into the e-mail the ticket arrives with.

A participant who has just been sent their ticket is exactly the person who
wants it on their phone, and the mail is where they are looking.  Indico offers
the passes on the registration page but says nothing about them in the mail.

The badges go in as embedded images rather than as links to artwork on the
server: most mail clients block remote images until the reader asks for them,
and a blocked button is a button nobody presses.  Indico already sends inline
images this way for registration pictures, so the shape is a known quantity.
"""

import re
from email.mime.image import MIMEImage

from markupsafe import Markup, escape

from indico.core import signals
from indico.modules.events.registration.models.registrations import RegistrationState
from indico.util.i18n import _
from indico.util.signals import values_from_signal
from indico.web.flask.util import url_for

from indico_stsa.wallet import badge_path


#: Where the badges are spliced into the finished mail: Indico's registration
#: e-mail is a card with a grey strip at the bottom, and this puts them at the
#: end of the card's content, just above that strip.
#:
#: Matching on the strip's own colour rather than on the whole tag, because the
#: rest of that line is layout that could reasonably be tweaked.  If Indico ever
#: changes the colour the badges simply go after the card instead of inside it,
#: which is untidy but still a working button -- see `_splice`.
FOOTER_RE = re.compile(r'<div[^>]*background:\s*#EBEBEB', re.IGNORECASE)

#: Rendered height, matching the web badges.  Mail clients need the height on
#: the tag as well as in the style: Outlook ignores CSS on images.
BADGE_HEIGHT = 48

#: Templates whose mail carries the ticket.  Indico attaches it to any mail to
#: the registrant for a completed registration, except the receipt one, which is
#: about an invoice and has nothing to do with a pass.
TICKET_TEMPLATES = {
    'registration_creation_to_registrant.html',
    'registration_modification_to_registrant.html',
    'registration_state_update_to_registrant.html',
}

VENDOR_LABELS = {
    'apple': _('Add to Apple Wallet'),
    'google': _('Add to Google Wallet'),
}

VENDOR_ENDPOINTS = {
    'apple': 'event_registration.ticket_apple_wallet',
    'google': 'event_registration.ticket_google_wallet',
}


def available_vendors(regform):
    """The wallets this form issues passes for, in the order they are shown."""
    return tuple(vendor for vendor in ('google', 'apple')
                 if getattr(regform, f'is_{vendor}_wallet_available', False))


def carries_ticket(registration, template_name, to_managers):
    """Whether this is the mail the participant's ticket is attached to.

    Mirrors the conditions in `_notify_registration`, so the badges turn up on
    exactly the mails the ticket does and on no others.  In particular an
    organizer who has switched ticket e-mails off does not start getting pass
    links instead.
    """
    if to_managers or template_name not in TICKET_TEMPLATES:
        return False
    regform = registration.registration_form
    if registration.state != RegistrationState.complete:
        return False
    if not (regform.tickets_enabled and regform.ticket_on_email):
        return False
    if registration.is_ticket_blocked:
        return False
    # An event whose tickets are issued by a plugin -- a check-in service, say
    # -- has no Indico ticket to add to a wallet.
    return not any(values_from_signal(signals.event.is_ticketing_handled.send(regform), single_value=True))


def _attachment(vendor, path, cid):
    image = MIMEImage(path.read_bytes(), 'png')
    image.add_header('Content-ID', f'<{cid}>')
    # `inline` is what tells a client to draw it in the body rather than list it
    # next to the ticket as a second file to download.
    image.add_header('Content-Disposition', 'inline', filename=f'{vendor}-wallet.png')
    return image


def _badge_html(vendor, href, cid):
    # `Markup` throughout: the rendered mail body is `Markup` too, and adding a
    # plain string to it escapes the string -- which shows the participant the
    # HTML source of a button instead of the button.
    label = escape(VENDOR_LABELS[vendor])
    return Markup(
        '<a href="{href}" style="text-decoration: none; display: inline-block; '
        'margin: 0 12px 12px 0; vertical-align: top;">'
        '<img src="cid:{cid}" alt="{label}" height="{height}" '
        'style="height: {height}px; width: auto; border: 0; display: block;">'
        '</a>'
    ).format(href=href, cid=cid, label=label, height=BADGE_HEIGHT)


def _block_html(badges):
    # Inline styles only, and the badges laid out as inline images rather than
    # in a table: Outlook lays flexbox out as if it were not there and strips
    # anything in a <style> block, and a fixed table of two badges runs off the
    # edge of the 600px card as soon as one language spells the label out at
    # length.  Inline images simply wrap onto a second line.
    return Markup(
        '<div style="padding: 0 20px 16px 20px; color: #555; font-family: Arial;">'
        '<p style="margin: 0 0 12px 0;">{lead}</p>'
        '<p style="margin: 0; line-height: 0;">{badges}</p>'
        '</div>'
    ).format(lead=_('You can also keep this ticket on your phone:'),
             badges=Markup('').join(badges))


def _splice(body, block):
    """Put `block` at the end of the card, or after everything if we cannot.

    `body` has to be `Markup`; slicing it keeps that, so the two halves and the
    block concatenate without anything being escaped.
    """
    match = FOOTER_RE.search(body)
    if match is None:
        return body + block
    return body[:match.start()] + block + body[match.start():]


def add_wallet_badges(email, registration, template_name, to_managers):
    """Add the badges to `email` in place.  Does nothing when they do not apply."""
    if not carries_ticket(registration, template_name, to_managers):
        return False

    badges = []
    for vendor in available_vendors(registration.registration_form):
        path = badge_path(vendor, 'png')
        if path is None:
            # No artwork for this vendor -- Apple's, normally.  Its guidelines
            # do not allow a stand-in, so the mail simply does not mention it.
            continue
        cid = f'stsa-wallet-{vendor}-{registration.id}'
        href = url_for(VENDOR_ENDPOINTS[vendor], registration.locator.registrant, _external=True)
        email['attachments'].append(_attachment(vendor, path, cid))
        badges.append(_badge_html(vendor, href, cid))

    if not badges:
        return False

    # The mail body is Jinja's own rendered output -- not anything anyone typed
    # -- and `get_template_module` already hands it over as `Markup`.  Saying so
    # again is what stops a plain string, from some future code path, being
    # escaped into the middle of somebody's confirmation.
    body = Markup(email['body'])  # ruff: ignore[unsafe-markup-use]
    email['body'] = _splice(body, _block_html(badges))
    return True
