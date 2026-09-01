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

import {registerPluginComponent, registerPluginObject} from 'indico/utils/plugins';

import GroupLoginGate from './GroupLoginGate';
import MemberDiscountField from './MemberDiscountField';
import MemberDiscountNotice from './MemberDiscountNotice';
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

document.addEventListener('DOMContentLoaded', setupWalletBadges);
