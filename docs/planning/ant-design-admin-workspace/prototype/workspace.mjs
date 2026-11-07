export const menus = {
  admin: [['sources', '资料与提取'], ['review', '候选审核'], ['canvas', '本体画布'], ['tree', '三级分类树'], ['schema', 'Schema 改进'], ['publish', '发布记录']],
  platform: [['generic', '通用本体'], ['tree', '通用三级树'], ['publish', '通用发布记录'], ['provision', '企业开通']],
  reader: [['canvas', '本体画布'], ['tree', '三级分类树']],
};
export const menuTab = (menu, role = 'admin') => ({ id: `menu:${menu}`, menu, title: menus[role].find(([id]) => id === menu)[1], type: 'menu', refresh: 0 });
export function initialWorkspace(role = 'admin') {
  const tab = menuTab(menus[role][0][0], role);
  return { tabs: [tab], active: tab.id };
}
export function openTab(state, tab) {
  return { tabs: state.tabs.some(t => t.id === tab.id) ? state.tabs : [...state.tabs, tab], active: tab.id };
}
export function closeTab(state, id, role = 'admin') {
  const index = state.tabs.findIndex(t => t.id === id);
  const tabs = state.tabs.filter(t => t.id !== id);
  if (!tabs.length) return initialWorkspace(role);
  return { tabs, active: state.active === id ? tabs[Math.min(index, tabs.length - 1)].id : state.active };
}
export function completeTab(state, id) {
  const completed = state.tabs.find(t => t.id === id);
  let tabs = state.tabs.filter(t => t.id !== id);
  if (!tabs.some(t => t.id === completed.origin.id)) tabs = [...tabs, completed.origin];
  return { tabs: tabs.map(t => t.id === completed.origin.id ? { ...t, refresh: (t.refresh || 0) + 1 } : t), active: completed.origin.id };
}
