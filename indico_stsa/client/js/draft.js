// Keeping a half-filled registration form across the trip to the login page.
//
// A participant who is told "sign in and you get the member discount" has
// usually typed a good deal already, and signing in is a full page navigation
// away and back.  So the answers are put in `sessionStorage` on the way out and
// read back on the way in.
//
// `sessionStorage` rather than `localStorage` on purpose: the draft belongs to
// this tab and this sitting, it never outlives the browser session, and it is
// removed the moment it has been restored.

const KEY_PREFIX = 'stsa-regform-draft';

//: A draft older than this is somebody's abandoned tab, not a login round
//: trip, and restoring it would overwrite a form they have started afresh.
const MAX_AGE_MS = 6 * 60 * 60 * 1000;

export function draftKey({eventId, regformId, registrationId}) {
  // The registration is part of the key so that a draft of a *new*
  // registration can never be restored over somebody editing an existing one:
  // both pages are the same form, on the same event, in the same tab.
  return `${KEY_PREFIX}:${eventId}:${regformId}:${registrationId || 'new'}`;
}

/**
 * Drop anything that cannot survive `JSON.stringify` and come back the same.
 *
 * File uploads are the reason this exists: a `File` stringifies to `{}`, which
 * would restore as an empty object over a field that expects a file and make
 * the form unsubmittable.  A file the participant picked before signing in is
 * lost either way -- the browser will not let us put it back -- so the honest
 * thing is to leave that field untouched and let them pick it again.
 */
export function serializableValues(values) {
  const clean = {};
  Object.entries(values || {}).forEach(([key, value]) => {
    if (!isSerializable(value)) {
      return;
    }
    clean[key] = value;
  });
  return clean;
}

function isSerializable(value) {
  if (value === null || value === undefined) {
    return true;
  }
  if (typeof File !== 'undefined' && value instanceof File) {
    return false;
  }
  if (typeof Blob !== 'undefined' && value instanceof Blob) {
    return false;
  }
  if (Array.isArray(value)) {
    return value.every(isSerializable);
  }
  if (typeof value === 'object') {
    return Object.values(value).every(isSerializable);
  }
  return typeof value !== 'function';
}

/** Put the current answers away. Returns whether anything was stored. */
export function saveDraft(config, values) {
  const clean = serializableValues(values);
  if (!Object.keys(clean).length) {
    return false;
  }
  try {
    sessionStorage.setItem(
      draftKey(config),
      JSON.stringify({ts: Date.now(), values: clean})
    );
    return true;
  } catch {
    // A full or disabled storage is not a reason to stop somebody registering.
    return false;
  }
}

/**
 * Take the stored answers back out, removing them as we go.
 *
 * One shot by design: restoring twice would undo edits made since the restore,
 * and a draft left lying around would resurface on a form the participant has
 * deliberately started over.
 */
export function takeDraft(config) {
  let raw;
  try {
    raw = sessionStorage.getItem(draftKey(config));
    sessionStorage.removeItem(draftKey(config));
  } catch {
    return null;
  }
  if (!raw) {
    return null;
  }
  let stored;
  try {
    stored = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!stored || typeof stored !== 'object' || !stored.values) {
    return null;
  }
  if (!stored.ts || Date.now() - stored.ts > MAX_AGE_MS) {
    return null;
  }
  return stored.values;
}

export function clearDraft(config) {
  try {
    sessionStorage.removeItem(draftKey(config));
  } catch {
    // nothing to do
  }
}
