// The member discount field, as the registration form's React side sees it.
//
// The value is the plugin's own bookkeeping: the server writes it, the field is
// locked against every other writer, and its only visible form is the named
// line it puts on the invoice. There is nothing here for an organizer to fill
// in, so the field renders no control at all -- only the marker its section is
// hidden by, in `styles/main.scss`.
//
// Registering it with core's field registry at all is what stops the form
// editor printing `Unknown input type: ext__stsa_member_discount`, which is how
// an organizer used to meet a field that was never meant for them.

import React from 'react';

export default function MemberDiscountField() {
  return <span hidden data-stsa-internal-field="" />;
}
