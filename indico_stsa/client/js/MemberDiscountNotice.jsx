// The notice above the registration form, and the draft that survives signing
// in.
//
// Rendered through core's `regformBeforeSections` entry point, which puts it
// inside the final-form context but above every section -- so it can reach the
// form's values, and a participant reads it before typing anything.

import React from 'react';
import {useForm} from 'react-final-form';
import {Message} from 'semantic-ui-react';

import {Translate} from 'indico/react/i18n';

import getConfig from './config';
import SignInButton from './SignInButton';
import {useDraft} from './useDraft';

import './stsa.module.scss';

/** What the discount is worth, in one sentence. */
function discountSummary({discountRate, discountAppliesTo}) {
  if (!discountRate) {
    return Translate.string('Members get money off. Sign in with your STSA membership to claim it.');
  }
  return discountAppliesTo === 'total'
    ? Translate.string(
        'STSA members get {rate} off the total price. Sign in with your membership to claim it.',
        {rate: discountRate}
      )
    : Translate.string(
        'STSA members get {rate} off the registration fee. Sign in with your membership to claim it.',
        {rate: discountRate}
      );
}

/**
 * The notice's headline: the most valuable thing signing in does here.
 *
 * The discount outranks the group gate, which outranks having the details
 * filled in -- that last one is a convenience, and the others are reasons to
 * sign in that cost somebody money or a feature if they do not.
 */
function noticeHeader({memberDiscount, groupLoginRequired}) {
  if (memberDiscount) {
    return Translate.string('Sign in to get the STSA member discount');
  }
  if (groupLoginRequired) {
    return Translate.string('Sign in to register as a group');
  }
  return Translate.string('Sign in to fill in your details');
}

export default function MemberDiscountNotice() {
  const config = getConfig();
  const form = useForm();
  // Mounted for its own sake: this is what carries the answers across the trip
  // to the login page, whether or not the notice below is shown.
  const saveDraftNow = useDraft(config, form);

  if (!config.anonymous || !config.loginUrl) {
    return null;
  }
  if (!config.memberDiscount && !config.groupLoginRequired && !config.profileFields) {
    return null;
  }

  return (
    <div styleName="notice">
      {/* `visible` is not decoration: Semantic hides `info`, `warning`,
          `success` and `error` messages inside a `.ui.form` unless the form
          itself carries that state, and the registration form is one. */}
      <Message info visible>
        <Message.Header>{noticeHeader(config)}</Message.Header>
        {config.noticeText ? (
          <p>{config.noticeText}</p>
        ) : (
          <>
            {config.memberDiscount && <p>{discountSummary(config)}</p>}
            {config.groupLoginRequired && (
              <p>
                <Translate>Creating or joining a group needs your STSA membership too.</Translate>
              </p>
            )}
            {config.profileFields && (
              <p>
                <Translate>
                  Signing in fills in your details on this form from your STSA membership.
                </Translate>
              </p>
            )}
          </>
        )}
        <SignInButton url={config.loginUrl} onNavigate={saveDraftNow} />
      </Message>
    </div>
  );
}
