"""Singapore Taiwanese Student Association customizations for Indico.

Three things STSA needs that core Indico does not provide:

* every outgoing e-mail carries STSA's own subject prefix instead of
  ``[Indico]``;
* a *member discount* that a signed-in participant earns on any registration
  form the organizers switch it on for, with the answers they have already
  typed surviving the trip through the login page;
* when the group registration plugin is installed, the option to restrict
  group registration to signed-in members.

An STSA membership is an account on this site, so a *member* is anyone signed
in and "becoming a member" is exactly "signing in".
"""

from indico.util.i18n import make_bound_gettext


__version__ = '0.1.0'

_ = make_bound_gettext('stsa')
