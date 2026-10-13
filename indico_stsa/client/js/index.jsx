// Wires the plugin's pieces into the pages that need them.
//
// `regformBeforeSections` is rendered once, above the whole registration form;
// it carries the "sign in for the member discount" notice and, more
// importantly, the draft that survives the trip to the login page.
//
// `regform-ext__group_plan-field-item` is rendered inside the group
// registration plugin's own form item, and only exists when that plugin has put
// its field on the form -- which is exactly when the group login gate has
// anything to gate.
//
// The wallet badges are not part of the React form at all; they replace
// server-rendered markup once the page is there.
//
// The member discount *field* is registered with core's field registry for the
// opposite reason to a normal field: an unregistered input type renders as
// `Unknown input type: ext__stsa_member_discount` wherever a manager sees the
// form, and this field is internal. See `MemberDiscountField`.
//
// The four member-detail fields are registered for the usual reason, and for a
// sharper one besides: the form editor's "show this field if" dropdown reads
// the registry for *every* item on the form with no guard for a type nobody
// registered, so a field type the server puts on a form and this file does not
// name does not render badly -- it throws, and takes the editor with it.
// `tests/test_client_registry.py` holds the two lists together.

import {registerPluginComponent, registerPluginObject} from 'indico/utils/plugins';

import GroupLoginGate from './GroupLoginGate';
import MemberDiscountField from './MemberDiscountField';
import MemberDiscountNotice from './MemberDiscountNotice';
import ProfileInput from './ProfileInput';
import setupWalletBadges from './wallet';

// Plugin field names must start with `ext__`; the core registry rejects
// anything else.
registerPluginComponent('stsa', 'regformBeforeSections', MemberDiscountNotice);
registerPluginComponent('stsa', 'regform-ext__group_plan-field-item', GroupLoginGate);

registerPluginObject('stsa', 'regformCustomFields', {
  name: 'ext__stsa_member_discount',
  // The registry asks every field for a title and an icon, for the "Add field"
  // dropdown -- which this one is then kept out of: the plugin provisions the
  // field itself, and a second copy would be a second invoice line that nothing
  // ever writes to.
  title: 'STSA member discount (internal)',
  icon: 'coins',
  hideFromItemDropdown: () => true,
  inputComponent: MemberDiscountField,
  // It draws its own (empty) form item rather than a labelled control, and
  // none of the standard field settings apply to a value only the server ever
  // writes.
  customFormItem: true,
  noLabel: true,
  noRequired: true,
  noRetentionPeriod: true,
  noInternalName: true,
});

// The member's own details.  `title` is what the "Add field" dropdown calls the
// type; `label` is what the new field is called until the organizer says
// otherwise, which saves them typing the one thing the type already tells us.
const PROFILE_FIELDS = [
  {name: 'ext__stsa_chinese_name', title: 'STSA 中文姓名', label: '中文姓名', icon: 'user'},
  {
    name: 'ext__stsa_english_name',
    title: 'STSA 英文姓名',
    label: '英文姓名',
    icon: 'sort-alpha-asc',
  },
  {name: 'ext__stsa_major', title: 'STSA 就讀科系', label: '就讀科系', icon: 'book'},
  {
    name: 'ext__stsa_year_of_study',
    title: 'STSA 目前身分',
    label: '目前身分',
    icon: 'user-reading',
  },
];

PROFILE_FIELDS.forEach(({name, title, label, icon}) => {
  registerPluginObject('stsa', 'regformCustomFields', {
    name,
    title,
    icon,
    inputComponent: ProfileInput,
    // Nothing to configure beyond the standard settings: the value is a plain
    // string and where it comes from is fixed by the type.
    settingsFormInitialData: {title: label},
  });
});

document.addEventListener('DOMContentLoaded', setupWalletBadges);
