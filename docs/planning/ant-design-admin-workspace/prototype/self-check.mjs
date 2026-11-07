import assert from 'node:assert/strict';
import { menus, menuTab, initialWorkspace, openTab, closeTab, completeTab } from './workspace.mjs';
for (const role of Object.keys(menus)) {
  const state = initialWorkspace(role);
  assert.equal(state.active, `menu:${menus[role][0][0]}`);
  assert.equal(closeTab(state, state.active, role).active, state.active);
}
const origin = menuTab('canvas');
const form = { id: 'knowledge:new', menu: 'canvas', type: 'editor', title: '新增本体条目', origin, dirty: true };
let state = openTab(initialWorkspace(), origin);
state = openTab(state, form);
assert.equal(openTab(state, { ...form, dirty: false }).tabs.length, 3);
assert.equal(openTab(state, { ...form, dirty: false }).tabs[2].dirty, true);
state = openTab(state, { ...form, id: 'knowledge:K-001' });
state = openTab(state, { ...form, id: 'knowledge:K-002' });
assert.equal(state.tabs.filter(t => t.type === 'editor').length, 3);
state = closeTab(state, origin.id);
state = completeTab(state, form.id);
assert.equal(state.active, origin.id);
assert.equal(state.tabs.find(t => t.id === origin.id).refresh, 1);
assert.equal(state.tabs.find(t => t.id === 'knowledge:K-001').dirty, true);
assert.equal(state.tabs.find(t => t.id === 'menu:sources').refresh, 0);
assert.equal(state.tabs.some(t => t.id === form.id), false);
// 来源是功能 tab 时，也必须返回该功能 tab，而不是它的所属菜单。
const nested = { ...form, id: 'relation:new', origin: { ...form, id: 'knowledge:K-003', dirty: true } };
state = completeTab(openTab(state, nested), nested.id);
assert.equal(state.active, 'knowledge:K-003');
assert.equal(state.tabs.find(t => t.id === 'knowledge:K-003').dirty, true);
console.log('通过：角色默认入口、末标签回落、实例复用、不同记录、来源重开与局部刷新、其他草稿保留。');
