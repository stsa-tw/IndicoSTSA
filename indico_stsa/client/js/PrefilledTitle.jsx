// The title a new member-detail field starts with.
//
// It is *not* `settingsFormInitialData`, though that is what it reads like.  Core's
// "Add new field" dialog keeps its Submit button disabled until the form is dirty,
// and a form that starts from its initial values is pristine -- so a field whose
// title arrived already filled in, and valid, came with a button nobody could press
// until they had changed something, anything.  Every core field type gets away
// with it because its title starts empty and has to be typed.
//
// Writing the title once the form exists is a change as far as final-form is
// concerned: the dialog opens with the title filled in and the button live.  It is
// done once, on mount, and never again -- the title is the organizer's to edit.
//
// It has to wait a tick.  The dialog's content and its Submit button mount in the
// same commit, and the button only subscribes to the form in an effect that runs
// after this one -- and `useFormState` drops the first notification it receives,
// taking it for the state it was rendered with.  A change made in between is
// therefore lost to the button, which stays disabled over a form that is no longer
// pristine.  (Core's own `DirtyInitialValue` defers for the same reason.)

import PropTypes from 'prop-types';
import {useEffect} from 'react';
import {useForm} from 'react-final-form';

/**
 * Make the component for the "field settings" slot of one field type.
 *
 * Core renders `regform-<type>-field-settings` inside the settings dialog both
 * when adding a field and when configuring one that exists; only the first is
 * ours to fill in, and an existing field arrives with its `id`.
 */
export default function makePrefilledTitle(title) {
  function PrefilledTitle({id}) {
    const form = useForm();
    const adding = id === null;

    useEffect(() => {
      if (!adding) {
        return undefined;
      }
      const timer = setTimeout(() => form.change('title', title));
      return () => clearTimeout(timer);
    }, [form, adding]);

    return null;
  }

  PrefilledTitle.propTypes = {
    id: PropTypes.number,
  };

  PrefilledTitle.defaultProps = {
    id: null,
  };

  return PrefilledTitle;
}
