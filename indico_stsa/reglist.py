"""What the registrant list's "Customize list" dialog must not offer.

The dialog offers every field on the form as a column an organizer can switch
on, walking `regform.sections` straight from the template
(`management/reglist_filter.html:102`), and core has no hook for leaving one out
-- `RegistrationFormSection.available_fields` exists for that template and
nothing else.  So the internal member discount field was offered there under its
manager-only section, as `Member discount (internal)` -> `Member discount`.  It
is the plugin's own bookkeeping: the server writes it, the field is locked
against every other writer, and its only visible form is the named line it puts
on the invoice.

Filtering it out happens in Flask's own `before_render_template`, which hands a
receiver the context of the template about to be rendered.  Nothing in core is
patched; two plugins doing this compose, because each only ever wraps what the
other left behind; and if the template is ever restructured the worst that
happens is the column comes back.

Forking the template was the obvious alternative and is not an option.  A
customization path replaces a core template wholesale
(`web/flask/app.py:setup_jinja_customization` appends every plugin's path to one
search path), and the group registration plugin has the same internal field and
the same need -- so the second plugin to want this file would silently lose to
the first.
"""

from indico_stsa.constants import MEMBER_DISCOUNT_FIELD
from indico_stsa.util import find_field


#: The template rendered by `RHRegistrationsListCustomize`.
REGLIST_FILTER_TEMPLATE = 'events/registration/management/reglist_filter.html'


class _SectionWithoutFields:
    """A section that does not admit to holding the fields we hide.

    Only `available_fields` is ours.  The dialog also reads `title` and
    `is_visible`, and anything else belongs to the section itself.
    """

    def __init__(self, section, hidden_ids):
        self._section = section
        self._hidden_ids = hidden_ids

    def __getattr__(self, name):
        return getattr(self._section, name)

    @property
    def available_fields(self):
        return [field for field in self._section.available_fields if field.id not in self._hidden_ids]


class _RegformWithoutFields:
    """The registration form as the column dialog is allowed to see it.

    Both section collections have to be wrapped: the dialog lists the enabled
    sections and, under a *Disabled sections* heading, the rest.
    """

    def __init__(self, regform, hidden_ids):
        self._regform = regform
        self._hidden_ids = hidden_ids

    def __getattr__(self, name):
        return getattr(self._regform, name)

    @property
    def sections(self):
        return [_SectionWithoutFields(section, self._hidden_ids) for section in self._regform.sections]

    @property
    def disabled_sections(self):
        return [_SectionWithoutFields(section, self._hidden_ids) for section in self._regform.disabled_sections]


def hide_internal_columns(context):
    """Take the internal discount field out of the column dialog's context.

    The template drops a section with no `available_fields` left of its own
    accord, which is what makes the whole manager-only section disappear rather
    than leaving an empty heading behind.
    """
    regform = context.get('regform')
    if regform is None:
        return
    field = find_field(regform, MEMBER_DISCOUNT_FIELD)
    if field is None:
        return
    hidden_ids = frozenset({field.id})
    context['regform'] = _RegformWithoutFields(regform, hidden_ids)
    # A column somebody had already switched on -- "Selection: All" was enough
    # to do it, since it clicks every hidden entry too -- would otherwise stay
    # on the list with nothing left to switch it off.  Dropping it here means
    # the next Apply also drops it from the stored configuration.
    context['visible_items'] = [item for item in context.get('visible_items') or () if item not in hidden_ids]
