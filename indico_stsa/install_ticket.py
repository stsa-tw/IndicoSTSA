"""Installing the STSA ticket into an Indico instance.

The template lives in the database, not in the plugin: `DesignerTemplate` rows
are what Indico prints from, and an organizer has to be able to see and tweak
one in the designer.  So the plugin carries the design and puts a copy in when
asked, rather than at import time -- a plugin that rewrote a template every time
Indico started would silently undo an organizer's edits.

Re-running is safe and is how an upgrade is applied: the template is found by
title and updated in place, so the events pointing at it keep pointing at it.
"""

from pathlib import Path

from indico.core.db import db
from indico.modules.categories import Category
from indico.modules.designer import TemplateType
from indico.modules.designer.models.images import DesignerImageFile
from indico.modules.designer.models.templates import DesignerTemplate

from indico_stsa.ticket import TEMPLATE_TITLE, build_data


BACKGROUND = Path(__file__).parent / 'static' / 'ticket' / 'background.png'


def find_template(category):
    return (DesignerTemplate.query
            .filter_by(category_id=category.id, title=TEMPLATE_TITLE)
            .first())


def _set_background(template):
    """Attach the furniture layer, replacing any copy from an earlier install."""
    old = template.background_image
    image = DesignerImageFile(filename='background.png', content_type='image/png',
                              template=template)
    with BACKGROUND.open('rb') as f:
        image.save(f)
    db.session.flush()
    template.background_image = image
    if old is not None:
        # The template only ever needs the current one; leaving the old rows
        # behind would grow the image table by one file per upgrade.
        db.session.delete(old)
    db.session.flush()


def install(category=None, *, set_as_default=True):
    """Create or refresh the ticket template.

    :param category: where the template lives; the root category by default,
                     which is what makes it available to every event.
    :param set_as_default: also make it the category's default ticket, so
                           events use it without anybody choosing it.
    :return: ``(template, created)``
    """
    if not BACKGROUND.is_file():
        raise RuntimeError(f'the ticket artwork is missing: {BACKGROUND}. '
                           'Run scripts/build-ticket-artwork.py')

    category = category or Category.get_root()
    template = find_template(category)
    created = template is None
    if created:
        template = DesignerTemplate(title=TEMPLATE_TITLE, type=TemplateType.badge,
                                    category=category)
        db.session.add(template)
        db.session.flush()

    template.data = build_data()
    _set_background(template)

    if set_as_default:
        # By id, not through the relationship.  The template points at the
        # category and the category would point back at the template, and
        # SQLAlchemy cannot order two rows that each wait on the other --
        # it raises CircularDependencyError instead.  The template is already
        # flushed by here, so its id is real.
        category.default_ticket_template_id = template.id
    db.session.flush()
    return template, created
