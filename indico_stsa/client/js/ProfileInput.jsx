// The four member-detail fields, as the registration form's React side sees
// them: a text box, which is filled in and locked when the server knows what
// the signed-in account says.
//
// Locking is core's own and needs nothing from here.  The server writes a
// `lockedReason` into the item's data, and `FormItem` takes it from there --
// the input arrives `disabled` and the padlock appears beside it.  What core
// has no idea of is the value, so that is `autofillValue`, which the server
// writes next to the reason and which this component puts into the form.
//
// It is put there continuously rather than once on mount, and that is the
// point of the `useField`: a value can be changed under a locked field by
// things that are not the participant -- a restored draft, a field a condition
// hides and shows again resets itself to its default -- and a padlock over the
// wrong answer is worse than no padlock.  The server writes the answer over
// the submission anyway, so this is about what the participant is shown being
// what they will get.

import PropTypes from 'prop-types';
import React, {useEffect} from 'react';
import {useField, useForm} from 'react-final-form';

import {FinalInput} from 'indico/react/forms';

export default function ProfileInput({htmlId, htmlName, disabled, isRequired, autofillValue}) {
  const form = useForm();
  const {
    input: {value},
  } = useField(htmlName, {subscription: {value: true}, allowNull: true});

  useEffect(() => {
    if (autofillValue && value !== autofillValue) {
      form.change(htmlName, autofillValue);
    }
  }, [autofillValue, value, form, htmlName]);

  return (
    <FinalInput
      id={htmlId}
      type="text"
      name={htmlName}
      required={isRequired}
      disabled={disabled}
    />
  );
}

ProfileInput.propTypes = {
  htmlId: PropTypes.string.isRequired,
  htmlName: PropTypes.string.isRequired,
  disabled: PropTypes.bool,
  isRequired: PropTypes.bool,
  /** What the signed-in account says; absent when the field is for typing in. */
  autofillValue: PropTypes.string,
};

ProfileInput.defaultProps = {
  disabled: false,
  isRequired: false,
  autofillValue: null,
};
