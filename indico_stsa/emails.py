"""Rewriting the subject prefix on every e-mail Indico sends.

Indico builds subjects from ``emails/base.txt`` and ``emails/base.html``, whose
``subject_prefix`` block is the literal ``[Indico]``.  A template override
could change that -- but only for the mails that actually go through those
templates, and only to a value fixed at deploy time.

So this hooks the one place *every* mail passes through instead:
``indico.core.notifications.make_email`` is decorated with
``@make_interceptable``, and an interception can look at the finished mail.
That covers core mails, plugin mails, and the ones built from a plain
``subject=`` string rather than a template.

Only a leading ``[Indico]`` is replaced.  Mails that deliberately carry no
prefix -- the room-booking ones set the block to empty -- are left exactly as
they are, because there is nothing there to replace.
"""

import re


#: The prefix core produces.  The optional ``@host`` part is the error-report
#: variant (``indico/modules/core/templates/emails/error_report.txt``); it is
#: replaced whole, since the server name it carries is in the mail body anyway.
INDICO_PREFIX_RE = re.compile(r'^\s*\[Indico(?:@[^\]\s]*)?\]\s*')


def rewrite_subject(subject, prefix):
    """Swap Indico's own subject prefix for `prefix`.

    Returns `subject` untouched when it does not start with Indico's prefix,
    which is what leaves the deliberately unprefixed mails alone.  An empty
    `prefix` strips the prefix without putting anything in its place.
    """
    if not subject:
        return subject
    match = INDICO_PREFIX_RE.match(subject)
    if match is None:
        return subject
    rest = subject[match.end():]
    prefix = (prefix or '').strip()
    if not prefix:
        return rest
    return f'{prefix} {rest}' if rest else prefix
