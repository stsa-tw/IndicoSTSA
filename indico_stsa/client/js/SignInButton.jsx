// The one call to action this plugin has.
//
// An anchor rather than a button element, styled as a Semantic button: it is a
// navigation to the login page, so middle-clicking it, copying it and opening
// it in a new tab all have to keep working.  `onClick` still fires on an
// ordinary click, which is where the half-filled form gets put away.

import PropTypes from 'prop-types';
import React from 'react';
import {Button, Icon} from 'semantic-ui-react';

import {Translate} from 'indico/react/i18n';

import './stsa.module.scss';

export default function SignInButton({url, onNavigate}) {
  if (!url) {
    return null;
  }
  return (
    <div styleName="actions">
      <Button
        as="a"
        href={url}
        onClick={onNavigate}
        primary
        size="large"
        icon
        labelPosition="left"
        styleName="sign-in"
      >
        <Icon name="sign-in" />
        <Translate>Sign in with your STSA membership</Translate>
      </Button>
      <span styleName="hint">
        <Translate>
          Everything you have filled in so far is kept, and you come straight back to this form.
        </Translate>
      </span>
    </div>
  );
}

SignInButton.propTypes = {
  url: PropTypes.string,
  onNavigate: PropTypes.func,
};

SignInButton.defaultProps = {
  url: null,
  onNavigate: undefined,
};
