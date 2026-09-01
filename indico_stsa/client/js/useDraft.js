// The hook that carries a half-filled registration form across the login page.
//
// It is separate from the notice that offers the button because the two have
// different lifetimes: the notice is only shown while somebody is signed out,
// and the restore has to happen once they are signed *in*.

import {useCallback, useEffect, useRef} from 'react';

import {clearDraft, saveDraft, takeDraft} from './draft';

//: Values that must never come back from a draft.  A captcha answer is only
//: valid for the challenge that was on screen when it was typed, and after a
//: round trip through the login page that challenge is gone.
const EPHEMERAL_FIELDS = ['captcha'];

/**
 * Restore a saved draft into `form`, and keep saving the answers away.
 *
 * @returns a callback that stores the answers immediately; hand it to the
 *          `onClick` of anything that navigates to the login page.
 */
export function useDraft(config, form) {
  const valuesRef = useRef({});
  const doneRef = useRef(false);
  const restoredRef = useRef(false);

  // Track the current answers through `form.subscribe` rather than
  // `useFormState`, so that typing does not re-render the caller on every
  // keystroke.
  useEffect(
    () =>
      form.subscribe(
        ({values, submitSucceeded}) => {
          valuesRef.current = values;
          if (submitSucceeded) {
            // The registration went through; there is no draft to come back
            // to, and leaving one would resurface on the next form in this tab.
            doneRef.current = true;
            clearDraft(config);
          }
        },
        {values: true, submitSucceeded: true}
      ),
    [config, form]
  );

  useEffect(() => {
    if (restoredRef.current || !config.draft) {
      return undefined;
    }
    restoredRef.current = true;
    const values = takeDraft(config);
    if (!values) {
      return undefined;
    }

    // The restore is deferred by a task on purpose, and this is the whole
    // reason the hook is not a one-liner.
    //
    // This component is rendered above the form's sections, so its mount effect
    // runs *before* the fields register themselves with final-form.  And
    // react-final-form's `useField` deliberately ignores the first callback it
    // gets from `registerField` -- it already captured the field's state during
    // render -- so a value written in that window is stored in the form but
    // never reaches the input.  It shows up as a form that submits the restored
    // answers while displaying the old ones, which is worse than not restoring
    // at all.
    //
    // A macrotask runs after every effect in the mounting commit, so by the
    // time this fires the fields are registered and a plain `change` reaches
    // them the way it would if the participant had typed it.
    const timeout = setTimeout(() => {
      form.batch(() => {
        Object.entries(values).forEach(([name, value]) => {
          if (!EPHEMERAL_FIELDS.includes(name)) {
            form.change(name, value);
          }
        });
      });
    }, 0);
    return () => clearTimeout(timeout);
  }, [config, form]);

  const save = useCallback(() => {
    if (doneRef.current || !config.anonymous || !config.draft) {
      return;
    }
    saveDraft(config, valuesRef.current);
  }, [config]);

  useEffect(() => {
    // `pagehide` rather than `beforeunload`: it fires for ordinary navigation
    // *and* when the page goes into the back/forward cache, so a participant
    // who signs in through the header menu -- or anywhere else -- is covered
    // just as well as one who follows the button in our own notice.
    window.addEventListener('pagehide', save);
    return () => window.removeEventListener('pagehide', save);
  }, [save]);

  return save;
}
