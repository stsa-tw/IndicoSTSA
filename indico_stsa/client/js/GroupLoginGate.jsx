// Closes the group registration plugin's plan picker to people who are not
// signed in, on forms where an organizer has asked for that.
//
// Rendered through core's `regform-ext__group_plan-field-item` entry point,
// which puts it directly under that plugin's own input, inside the same form
// item.  So this does not have to know anything about how the picker is built
// -- only where it is, and what its value looks like when somebody has chosen
// a group.
//
// The server refuses the same choice again when the registration is submitted
// (`indico_stsa.handlers.enforce_group_login`).  This is the half that makes
// the rule visible rather than the half that enforces it.

import PropTypes from 'prop-types';
import React, {useEffect, useRef} from 'react';
import {useField, useForm} from 'react-final-form';
import {Message} from 'semantic-ui-react';

import {Translate} from 'indico/react/i18n';

import getConfig from './config';
import SignInButton from './SignInButton';
import {useDraft} from './useDraft';

import './stsa.module.scss';

//: What the picker holds when nobody has chosen anything.  Written rather than
//: cleared, because the picker reads `value.mode` on every render.
const NO_GROUP = {mode: 'none', plan: null, name: '', code: '', accepted: false};

/** Take the picker out of reach, and say so to a screen reader. */
function useDisabledPicker(active, ref) {
  useEffect(() => {
    const picker = active ? ref.current?.parentElement?.querySelector('[data-mode]') : null;
    if (!picker) {
      return undefined;
    }
    // `inert` and not `pointer-events`: it also takes the controls out of the
    // tab order and hides them from assistive technology, which is the whole
    // of "you cannot use this right now" rather than just the mouse half.
    picker.setAttribute('inert', '');
    picker.style.opacity = '0.5';
    return () => {
      picker.removeAttribute('inert');
      picker.style.opacity = '';
    };
  }, [active, ref]);
}

export default function GroupLoginGate({htmlName}) {
  const config = getConfig();
  const form = useForm();
  const ref = useRef(null);
  const active = config.groupLoginRequired && config.anonymous;

  const {
    input: {value},
  } = useField(htmlName, {subscription: {value: true}, allowNull: true});
  const mode = value?.mode;

  useDisabledPicker(active, ref);
  const saveDraftNow = useDraft(config, form);

  useEffect(() => {
    // A join link arrives as `?group_code=...` and the picker pre-fills itself
    // from it, so there is a value to clear here even though the controls are
    // out of reach.
    if (active && mode && mode !== 'none') {
      form.change(htmlName, {...NO_GROUP});
    }
  }, [active, mode, form, htmlName]);

  if (!active) {
    return null;
  }

  return (
    <div ref={ref} styleName="gate">
      {/* `visible` is not decoration: Semantic hides `warning` messages inside
          a `.ui.form` unless the form itself carries that state, and the
          registration form is one -- without it this box is in the DOM and
          invisible, which is the worst of both. */}
      <Message warning visible>
        <Message.Header>
          <Translate>Groups are for STSA members</Translate>
        </Message.Header>
        <p>
          <Translate>
            Only STSA members can create or join a group on this form. You can still register on your
            own without signing in.
          </Translate>
        </p>
        <SignInButton url={config.loginUrl} onNavigate={saveDraftNow} />
      </Message>
    </div>
  );
}

GroupLoginGate.propTypes = {
  htmlName: PropTypes.string.isRequired,
};
