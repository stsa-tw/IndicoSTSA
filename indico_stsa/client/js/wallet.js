// Replaces Indico's "Add to Wallet" controls with the standard Apple and
// Google badges.
//
// Core offers the two passes either as a dropdown ("Add to Wallet" with
// "Google Wallet" and "Apple Wallet/Passbook" inside it) or, when only one of
// them is configured, as an ordinary Indico button.  Neither is what a
// participant looks for: people recognise the badges, and Apple's and Google's
// own guidelines ask for them.
//
// This runs over the finished page rather than forking core's templates.  The
// registration summary is a 300-line template that changes between Indico
// releases, and a fork of it would have to be reviewed on every upgrade for the
// sake of two buttons.  Working on the DOM also fails safely: if core ever
// moves these endpoints, the links this looks for are simply not found and the
// participant keeps the buttons Indico shipped.

//: The endpoints core points the two passes at.  Matched on the URL rather than
//: on a class or the link text, because the URL is what identifies them.
const WALLETS = [
  {
    key: 'google',
    pattern: /\/ticket\/google-wallet(\?|$)/,
    label: 'Add to Google Wallet',
  },
  {
    key: 'apple',
    pattern: /\/ticket\/apple-wallet(\?|$)/,
    label: 'Add to Apple Wallet',
  },
];

const BADGE_ROW_CLASS = 'stsa-wallet-badges';

function badgeFor(wallet, href, imageUrl) {
  const link = document.createElement('a');
  link.className = `stsa-wallet-badge stsa-wallet-badge--${wallet.key}`;
  link.href = href;
  link.setAttribute('aria-label', wallet.label);

  const img = document.createElement('img');
  img.src = imageUrl;
  // The link already carries the label, so repeating it here would make a
  // screen reader read the same sentence twice.
  img.alt = '';
  img.setAttribute('aria-hidden', 'true');
  link.appendChild(img);
  return link;
}

/**
 * The row the badges go in, created once per action box.
 *
 * It goes *after* the whole box rather than inside its toolbar, which is the
 * obvious place and the wrong one.  Indico lays that toolbar out as a single
 * non-wrapping flex row inside a flex `.section` that also holds an icon and a
 * sentence of text, sized for its own 30px buttons.  Two badges are wider than
 * the control they replace, so putting them in there pushes the toolbar past
 * the edge of the box and slides the second badge out under the border.
 *
 * A row of its own also suits them better: these are the standard badges people
 * look for, not another Indico button.
 */
function badgeRow(link) {
  const anchor = link.closest('.action-box') || link.closest('.toolbar') || link.parentElement;
  const next = anchor.nextElementSibling;
  if (next && next.classList.contains(BADGE_ROW_CLASS)) {
    return next;
  }
  const row = document.createElement('div');
  row.className = BADGE_ROW_CLASS;
  anchor.parentElement.insertBefore(row, anchor.nextSibling);
  return row;
}

/**
 * A dropdown that existed only for the wallet links has to go too.
 *
 * Core's "Add to Wallet" dropdown holds nothing else, so once the badges are
 * out of it an empty menu and a button that opens onto nothing would be left
 * behind.  The "Get ticket" dropdown on the conference home page also holds the
 * PDF, so it stays.
 */
function dropEmptyDropdown(dropdown) {
  if (!dropdown || dropdown.querySelector('li')) {
    return;
  }
  const toggle = dropdown.previousElementSibling;
  if (toggle && toggle.hasAttribute('data-toggle')) {
    toggle.remove();
  }
  dropdown.remove();
}

/**
 * Where a vendor's badge artwork lives, or nothing.
 *
 * The plugin puts one tag per vendor in the document head on every request, so
 * a change in the admin area takes effect on the next page load rather than
 * whenever some cache happens to be rebuilt.  A vendor with no tag has no
 * artwork installed and is left alone -- Apple's badge has to be downloaded by
 * hand, and its guidelines forbid substituting anything else for it.
 */
function artworkFor(key) {
  return document.querySelector(`meta[name="stsa-wallet-${key}"]`)?.content || null;
}

export default function setupWalletBadges() {
  const emptiedDropdowns = new Set();
  const links = [...document.querySelectorAll('a[href]')];

  WALLETS.forEach(wallet => {
    const image = artworkFor(wallet.key);
    if (!image) {
      return;
    }
    links.forEach(link => {
      if (!wallet.pattern.test(link.getAttribute('href') || '')) {
        return;
      }
      if (link.closest(`.${BADGE_ROW_CLASS}`)) {
        // A badge this function already made.  It points at the same endpoint
        // as the link it replaced, so without this a second run would "replace"
        // it with a copy of itself and leave the first row behind, empty.
        return;
      }
      const item = link.closest('li');
      const dropdown = item && item.closest('.i-dropdown');

      badgeRow(dropdown || link).appendChild(badgeFor(wallet, link.href, image));
      (item || link).remove();
      if (dropdown) {
        emptiedDropdowns.add(dropdown);
      }
    });
  });

  emptiedDropdowns.forEach(dropEmptyDropdown);
}
