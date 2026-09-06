"""Singapore Taiwanese Student Association customizations for Indico.

Seven things STSA needs that core Indico does not provide:

* every outgoing e-mail carries STSA's own subject prefix instead of
  ``[Indico]``;
* a *member discount* that a signed-in participant earns on any registration
  form the organizers switch it on for, with the answers they have already
  typed surviving the trip through the login page;
* when the group registration plugin is installed, the option to restrict
  group registration to signed-in members;
* Apple's and Google's own wallet badges in place of Indico's dropdown, on the
  registration page and in the e-mail the ticket arrives with;
* an STSA ticket design, and a font that can actually draw Chinese on it;
* a one-click payment reminder to everybody on a registration form whose fee is
  still outstanding, each mail naming what that person owes;
* the registration form's e-mail field held to the address on the membership of
  whoever is signed in, so that the registrations a member makes can always be
  matched back to them.

An STSA membership is an account on this site, so a *member* is anyone signed
in and "becoming a member" is exactly "signing in".
"""

from indico.util.i18n import make_bound_gettext


__version__ = '0.2.8'

_ = make_bound_gettext('stsa')
