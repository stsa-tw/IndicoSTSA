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

import {registerPluginComponent} from 'indico/utils/plugins';

import GroupLoginGate from './GroupLoginGate';
import MemberDiscountNotice from './MemberDiscountNotice';
import setupWalletBadges from './wallet';

// Plugin field names must start with `ext__`; the core registry rejects
// anything else.
registerPluginComponent('stsa', 'regformBeforeSections', MemberDiscountNotice);
registerPluginComponent('stsa', 'regform-ext__group_plan-field-item', GroupLoginGate);

document.addEventListener('DOMContentLoaded', setupWalletBadges);
