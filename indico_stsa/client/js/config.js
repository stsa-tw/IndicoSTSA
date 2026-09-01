// Everything the React side needs arrives as one `data-stsa` attribute on the
// registration form's root element, put there by the plugin's
// `regform-container-attrs` template hook.  Reading it straight off the DOM
// rather than out of the redux store keeps this independent of core's
// selectors, which are not part of the plugin API.

const ROOT_ID = 'registration-form-submission-container';

const EMPTY = {
  anonymous: false,
  draft: false,
  eventId: null,
  regformId: null,
  registrationId: null,
  loginUrl: null,
  memberDiscount: false,
  discountRate: '',
  discountAppliesTo: null,
  noticeText: '',
  groupLoginRequired: false,
};

let cached = null;

/** The plugin's configuration for the registration form on this page. */
export default function getConfig() {
  if (cached !== null) {
    return cached;
  }
  const root = document.getElementById(ROOT_ID);
  const raw = root?.dataset?.stsa;
  if (!raw) {
    cached = EMPTY;
    return cached;
  }
  try {
    cached = {...EMPTY, ...JSON.parse(raw)};
  } catch {
    // A form we cannot read the configuration for is a form this plugin stays
    // out of the way of; it must never be a form nobody can register on.
    cached = EMPTY;
  }
  return cached;
}
