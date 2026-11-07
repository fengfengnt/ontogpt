// 设计评审草图：比较同一套已确定布局在三种主题下的效果；所有业务操作仅修改内存中的模拟数据。
import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import { App as AntApp, ConfigProvider, theme as antTheme, Menu, Tabs, Breadcrumb, Button, Dropdown, Input, Select, Segmented, Tag, Avatar, Badge, Table, Space, Tree, TreeSelect, Form, Alert, Descriptions, Collapse, Timeline, Checkbox, Empty, Divider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { FileTextOutlined, AuditOutlined, ApartmentOutlined, ClusterOutlined, ExperimentOutlined, HistoryOutlined, PlusOutlined, SearchOutlined, ReloadOutlined, QuestionCircleOutlined, SunOutlined, MoonOutlined, SafetyCertificateOutlined, CheckCircleOutlined, ArrowLeftOutlined, LinkOutlined, InfoCircleOutlined, UserOutlined, BankOutlined, FolderOutlined, SaveOutlined, DownOutlined, MenuFoldOutlined, MenuUnfoldOutlined } from '@ant-design/icons';
import { menus, menuTab, initialWorkspace, openTab, closeTab, completeTab } from './workspace.mjs';

const palettes = {
  light: { label: '浅色', bg: '#f4f6f9', panel: '#ffffff', subtle: '#edf2fc', text: '#233048', muted: '#68768c', border: '#e4e9f0', primary: '#285bce', edge: '#a9b8cf', 'on-primary': '#ffffff' },
  dark: { label: '暗黑', bg: '#121720', panel: '#1c2432', subtle: '#263247', text: '#e7edf6', muted: '#a2afc4', border: '#354155', primary: '#84a7ff', edge: '#596b88', 'on-primary': '#12213d' },
  green: { label: '绿色护眼', bg: '#e9f0e6', panel: '#f6f9f2', subtle: '#e0ecdf', text: '#283e30', muted: '#5c7260', border: '#d1decd', primary: '#3d7051', edge: '#92ac91', 'on-primary': '#ffffff' },
};
const icons = { sources: FileTextOutlined, review: AuditOutlined, canvas: ApartmentOutlined, tree: ClusterOutlined, schema: ExperimentOutlined, publish: HistoryOutlined, generic: ApartmentOutlined, provision: BankOutlined };
const themeOptions = [{ key: 'light', label: '浅色', icon: <SunOutlined /> }, { key: 'dark', label: '暗黑', icon: <MoonOutlined /> }, { key: 'green', label: '护眼', icon: <SafetyCertificateOutlined /> }];
const roleLabels = { admin: '企业管理员', platform: '平台管理员', reader: '只读用户' };
const treeData = [{ title: '信息化采购', key: 'it', value: 'it', selectable: false, children: [{ title: '计算机设备', key: 'computer', value: 'computer', selectable: false, children: [{ title: '笔记本电脑', key: 'notebook', value: 'notebook' }, { title: '台式机电脑', key: 'desktop', value: 'desktop' }] }] }];
const initialSources = [
  { id: 'SRC-001', name: '终端设备采购技术规范', format: 'Markdown', date: '2026-10-22', status: '已提取', count: 16, content: '笔记本电脑属于计算机设备，相关要求按适用项目分别审核确认。' },
  { id: 'SRC-002', name: '办公电脑配置补充说明', format: '文本', date: '2026-10-22', status: '待提取', count: 0, content: '办公电脑包括笔记本电脑与台式机电脑，设备配置以经确认的项目要求为准。' },
  { id: 'SRC-003', name: '设备交付与验收要求', format: 'Markdown', date: '2026-10-21', status: '已提取', count: 8, content: '设备交付时，应依据该项目中已确认的要求核对验收材料。' },
];
const initialItems = [
  { id: 'K-001', name: '办公笔记本电脑', kind: '设备类型', category: 'notebook', status: '已发布', description: '用于办公场景的笔记本电脑。具体配置由适用项目的要求确定。', source: 'SRC-001', evidence: '笔记本电脑属于计算机设备，相关要求按适用项目分别审核确认。', scope: '电脑品类 · 办公场景' },
  { id: 'K-002', name: '设备交付验收', kind: '采购要求', category: 'notebook', status: '已发布', description: '按具体项目已确认的要求核对验收材料。', source: 'SRC-003', evidence: '设备交付时，应依据该项目中已确认的要求核对验收材料。', scope: '交付与验收阶段' },
  { id: 'K-003', name: '台式机电脑', kind: '设备类型', category: 'desktop', status: '已发布', description: '办公电脑中的台式机设备类型。', source: 'SRC-002', evidence: '办公电脑包括笔记本电脑与台式机电脑。', scope: '电脑品类' },
];
const titles = { source: '资料', knowledge: '本体条目', relation: '本体关系', provision: '企业' };
const emptyValues = { source: { name: '', format: 'Markdown', content: '', notes: '' }, knowledge: { name: '', kind: '设备类型', category: 'notebook', description: '', source: 'SRC-001', evidence: '', scope: '', notes: '' }, relation: { name: '', subject: 'K-001', object: 'K-002', source: 'SRC-003', evidence: '', notes: '' }, provision: { name: '', company: '', username: '' } };
function initialTheme() { try { const saved = localStorage.getItem('ontogpt-workspace-prototype.theme'); return palettes[saved] ? saved : 'light'; } catch { return 'light'; } }
function Prototype() {
  const [theme, setTheme] = useState(initialTheme);
  const p = palettes[theme];
  const tokens = { colorPrimary: p.primary, colorBgBase: p.panel, colorBgContainer: p.panel, colorBgLayout: p.bg, colorText: p.text, colorTextSecondary: p.muted, colorBorder: p.border, colorBorderSecondary: p.border, colorFillAlter: p.subtle, borderRadius: 6, fontFamily: '"Segoe UI","Microsoft YaHei UI",sans-serif', fontSize: 13, controlHeight: 34 };
  function changeTheme(next) { setTheme(next); try { localStorage.setItem('ontogpt-workspace-prototype.theme', next); } catch {} }
  return <ConfigProvider locale={zhCN} theme={{ algorithm: theme === 'dark' ? antTheme.darkAlgorithm : antTheme.defaultAlgorithm, token: tokens, components: { Menu: { itemSelectedBg: p.subtle, itemSelectedColor: p.primary, collapsedWidth: 64 }, Table: { headerBg: p.subtle }, Tabs: { cardBg: p.panel } } }}><AntApp><Workspace theme={theme} changeTheme={changeTheme} palette={p} /></AntApp></ConfigProvider>;
}
function Workspace({ theme, changeTheme, palette }) {
  const { modal, message } = AntApp.useApp();
  const [role, setRole] = useState('admin');
  const [collapsed, setCollapsed] = useState(false);
  const [workspace, setWorkspace] = useState(initialWorkspace);
  const [sources, setSources] = useState(initialSources);
  const [items, setItems] = useState(initialItems);
  const [failNext, setFailNext] = useState(false);
  const [notice, setNotice] = useState('');
  const [pending, setPending] = useState([]);
  const current = workspace.tabs.find(t => t.id === workspace.active);
  function navigate(menu) { setNotice(''); setWorkspace(s => openTab(s, menuTab(menu, role))); }
  function edit(kind, record, origin = current, candidate = false) {
    const values = Object.fromEntries(Object.entries(emptyValues[kind]).map(([key, value]) => [key, record?.[key] ?? value]));
    const id = `${kind}:${candidate ? 'candidate-' : ''}${record?.id || 'new'}`;
    setWorkspace(s => openTab(s, { id, menu: origin.menu, title: candidate ? `修订：${record.name}` : record ? `编辑：${record.name}` : `新增${titles[kind]}`, type: 'editor', kind, recordId: record?.id, candidate, initial: values, draft: values, dirty: false, origin: { ...origin }, refresh: 0 }));
  }
  function updateDraft(id, values) { setWorkspace(s => ({ ...s, tabs: s.tabs.map(t => t.id === id ? { ...t, draft: values, dirty: JSON.stringify(values) !== JSON.stringify(t.initial) } : t) })); }
  function requestClose(id) {
    const tab = workspace.tabs.find(t => t.id === id);
    const close = () => setWorkspace(s => closeTab(s, id, role));
    if (tab.dirty) modal.confirm({ title: '放弃未提交的修改？', content: `“${tab.title}”中有未提交内容，关闭后将丢弃。`, okText: '放弃修改并关闭', cancelText: '继续编辑', okButtonProps: { danger: true }, onOk: close }); else close();
  }
  function save(tab, values) {
    if (failNext) { setFailNext(false); message.error('模拟提交失败：内容已保留，请继续编辑或重试。'); return; }
    if (tab.kind === 'source') {
      const row = { ...values, id: tab.recordId || `SRC-${String(sources.length + 1).padStart(3, '0')}`, date: '2026-10-23', status: '待提取', count: 0 };
      setSources(rows => tab.recordId ? rows.map(r => r.id === tab.recordId ? row : r) : [...rows, row]);
    } else if (tab.kind === 'knowledge') {
      const row = { ...values, id: tab.recordId || `K-${String(items.length + 1).padStart(3, '0')}`, status: '待发布' };
      setItems(rows => tab.recordId ? rows.map(r => r.id === tab.recordId ? row : r) : [...rows, row]);
    }
    if (tab.kind !== 'source') setPending(rows => [...rows, { id: `CHANGE-${rows.length + 1}`, name: values.name, kind: titles[tab.kind], status: '待发布' }]);
    setWorkspace(s => completeTab(s, tab.id));
    setNotice(`已模拟保存“${values.name}”，已返回并刷新“${tab.origin.title}”。${tab.kind === 'source' ? '可在列表中查看新资料。' : '本体变更尚未发布。'}`);
    message.success('已模拟保存，并刷新来源页');
  }
  function changeRole(next) {
    const change = () => { setRole(next); setWorkspace(initialWorkspace(next)); setNotice(''); };
    if (workspace.tabs.some(t => t.dirty)) modal.confirm({ title: '切换预览身份？', content: '切换身份会清空本次打开的标签和未提交草稿。', okText: '切换身份', cancelText: '保留当前身份', onOk: change }); else change();
  }
  function showHelp() {
    modal.info({ title: '设计评审 · 可体验的交互', width: 620, icon: <ExperimentOutlined />, content: <><ol className="help-list"><li>点击不同菜单，已有 tab 会复用，内容保留。</li><li>在“本体画布”点“新增条目”，填写后切换菜单或主题。</li><li>关闭未提交表单会询问是否放弃。</li><li>关闭来源 tab 后提交，来源页将自动重开并刷新。</li><li>关闭所有 tab，将回到当前角色首个有权限的菜单。</li><li>刷新浏览器只记住主题，不恢复草稿和模拟数据。</li></ol><Divider /><p>预览身份（仅影响草图中的菜单与默认入口）</p><Select aria-label="预览身份" defaultValue={role} style={{ width: '100%' }} options={Object.entries(roleLabels).map(([value, label]) => ({ value, label }))} onChange={changeRole} /><p style={{ marginTop: 18 }}><Checkbox defaultChecked={failNext} onChange={e => setFailNext(e.target.checked)}>模拟下一次提交失败，检查内容是否保留</Checkbox></p></>, okText: '开始体验' });
  }
  const props = { role, sources, items, edit, navigate, pending, message, modal, setSources, setPending };
  return <div className="shell" data-theme={theme} style={Object.fromEntries(Object.entries(palette).map(([k, v]) => [`--${k}`, v]))}>
    <div className="preview-strip"><div><span className="preview-label"><ExperimentOutlined /> 设计评审草图</span><span className="preview-detail">所有内容均为模拟数据，操作不会写入业务系统</span></div><span>ONTOGPT · V0.3</span></div>
    <header className="topbar"><div className="topbar-left"><div className="brand"><div className="brand-mark">知</div><div><strong>采购知识工作台</strong><small>ONTOGPT / KNOWLEDGE</small></div></div><div className="header-context"><div className="topbar-title">{role === 'platform' ? '通用模板管理' : '企业独立知识空间'}</div><div className="topbar-meta">电脑（台式机 / 笔记本）<span style={{ marginInline: 9 }}>·</span>{role === 'platform' ? '平台通用基线' : '当前已发布版本 v1'}</div></div></div><div className="topbar-tools"><Dropdown trigger={['click']} placement="bottomRight" menu={{ selectable: true, selectedKeys: [theme], items: themeOptions, onClick: ({ key }) => changeTheme(key) }}><Button className="theme-button" aria-label={`主题：${themeOptions.find(option => option.key === theme).label}`} icon={themeOptions.find(option => option.key === theme).icon}>主题 <DownOutlined /></Button></Dropdown><Button aria-label="交互说明与预览身份" icon={<QuestionCircleOutlined />} onClick={showHelp} /></div></header>
    <div className="shell-body"><aside className={`sidebar${collapsed ? ' sidebar-collapsed' : ''}`}><div className="sidebar-heading">{!collapsed && <span className="nav-caption">{role === 'platform' ? '平台管理' : '企业知识空间'}</span>}<Button type="text" aria-label={collapsed ? '展开菜单' : '收起菜单'} title={collapsed ? '展开菜单' : '收起菜单'} aria-expanded={!collapsed} aria-controls="workspace-menu" icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />} onClick={() => setCollapsed(value => !value)} /></div>
      <nav className="menu-scroll" aria-label="侧栏菜单滚动区"><Menu id="workspace-menu" mode="inline" inlineCollapsed={collapsed} aria-label="工作区菜单" selectedKeys={[current.menu]} onClick={({ key }) => navigate(key)} items={menus[role].map(([key, label]) => ({ key, label, title: label, 'aria-label': label, icon: React.createElement(icons[key]) }))} /></nav>
      <div className="sidebar-foot">{!collapsed && <div className="version-note"><SafetyCertificateOutlined /> {role === 'platform' ? '通用版本用于新企业初始化' : '企业数据独立隔离'}<br />{role === 'reader' ? '仅查看已发布知识' : '有来源 · 可审核 · 按版本发布'}</div>}<div className="identity"><Avatar size={34} icon={<UserOutlined />} title={roleLabels[role]} aria-label={roleLabels[role]} />{!collapsed && <div><strong>{role === 'platform' ? '平台空间' : '演示企业'}</strong><small>{roleLabels[role]}</small></div>}</div></div>
    </aside><main className="main" aria-label="标签页工作区">
      <Tabs className="workspace-tabs" type="editable-card" hideAdd activeKey={workspace.active} onChange={active => { setNotice(''); setWorkspace(s => ({ ...s, active })); }} onEdit={(id, action) => action === 'remove' && requestClose(id)} destroyOnHidden={false}
        items={workspace.tabs.map(tab => ({ key: tab.id, forceRender: true, label: <span className="tab-label">{tab.type === 'editor' ? <FileTextOutlined /> : React.createElement(icons[tab.menu])}{tab.title}{tab.dirty && <span className="dirty-dot" aria-label="未提交修改" />}</span>, closeIcon: <span aria-label={`关闭 ${tab.title}`}>×</span>, children: <div className="page"><Breadcrumb items={[{ title: role === 'platform' ? '平台管理' : '企业知识空间' }, { title: <a onClick={() => navigate(tab.menu)}>{menus[role].find(([key]) => key === tab.menu)[1]}</a> }, ...(tab.type === 'editor' ? [{ title: tab.title }] : [])]} />
          {notice && tab.id === workspace.active && <Alert style={{ marginBottom: 18 }} type="success" closable onClose={() => setNotice('')} title={notice} showIcon />}
          {tab.type === 'editor' ? <Editor tab={tab} sources={sources} items={items} onChange={v => updateDraft(tab.id, v)} onSave={v => save(tab, v)} onClose={() => requestClose(tab.id)} /> : <MenuPage tab={tab} {...props} />}
        </div> }))} />
      <div className="status-line" aria-live="polite" style={{ padding: '0 28px 12px' }}>{workspace.tabs.filter(t => t.dirty).length > 0 && `${workspace.tabs.filter(t => t.dirty).length} 个标签含未提交修改`}</div>
    </main></div>
  </div>;
}
function Heading({ title, subtitle, children }) { return <div className="page-heading"><div><h1>{title}</h1><p>{subtitle}</p></div><div className="page-actions">{children}</div></div>; }
function RefreshNote({ tab }) { return <span className="refresh-note" aria-live="polite">{tab.refresh > 0 ? `来源数据已刷新 ${tab.refresh} 次` : '模拟数据'}</span>; }
function Sources({ tab, sources, edit, navigate, message, setSources }) {
  const [search, setSearch] = useState(''); const [status, setStatus] = useState('全部状态');
  return <><Heading title="资料与提取" subtitle="汇集企业原始资料，提取有来源、可核对的采购知识。"><Tag icon={<SafetyCertificateOutlined />}>仅企业内部可见</Tag><Button type="primary" icon={<PlusOutlined />} onClick={() => edit('source')}>录入资料</Button></Heading>
    <div className="stats">{[['资料总数', sources.length, '份', '原始资料独立留存'], ['已完成提取', sources.filter(s => s.status === '已提取').length, '份', '提取结果需人工审核'], ['待审核候选', sources.reduce((n, s) => n + s.count, 0), '项', '审核通过后方可进入发布']].map(([label, value, unit, note]) => <div className="stat" key={label}><div className="stat-label">{label}</div><div className="stat-value">{value}<span className="stat-unit">{unit}</span></div><div className="stat-note">{note}</div></div>)}</div>
    <section className="surface"><div className="surface-head"><h2>企业资料</h2><RefreshNote tab={tab} /></div><div className="filters"><div className="filter-controls"><Input aria-label="搜索资料名称" prefix={<SearchOutlined />} placeholder="搜索资料名称" value={search} onChange={e => setSearch(e.target.value)} allowClear style={{ width: 250 }} /><Select aria-label="资料状态" value={status} onChange={setStatus} style={{ width: 128 }} options={['全部状态', '已提取', '待提取'].map(value => ({ value }))} /></div><Button icon={<ReloadOutlined />} onClick={() => message.info('当前为本地模拟数据，无需连接服务')}>刷新</Button></div>
      <Table rowKey="id" scroll={{ x: 710 }} pagination={{ pageSize: 5, showTotal: total => `共 ${total} 份资料` }} dataSource={sources.filter(s => s.name.includes(search) && (status === '全部状态' || s.status === status))} columns={[
        { title: '资料名称', dataIndex: 'name', width: 285, render: (name, row) => <><div className="cell-title"><FileTextOutlined style={{ color: 'var(--primary)', marginRight: 9 }} />{name}</div><div className="cell-meta">{row.id} · {row.format}</div></> },
        { title: '录入日期', dataIndex: 'date', width: 110 }, { title: '状态', dataIndex: 'status', width: 95, render: v => <Tag color={v === '已提取' ? 'success' : 'default'}>{v}</Tag> }, { title: '候选', dataIndex: 'count', width: 70 },
        { title: '操作', width: 160, render: (_, row) => <Space size={2}><Button type="link" size="small" onClick={() => edit('source', row)}>查看资料</Button><Button type="link" size="small" onClick={() => row.status === '已提取' ? navigate('review') : (setSources(rows => rows.map(r => r.id === row.id ? { ...r, status: '已提取', count: 3 } : r)), message.success('已生成模拟候选，可前往候选审核'))}>{row.status === '已提取' ? '查看候选' : '模拟提取'}</Button></Space> },
      ]} /></section><div className="page-hint"><InfoCircleOutlined /> 提取结果首先形成候选，须核对证据后审核发布。此处均为虚构示例材料。</div>
  </>;
}
function TreePage({ tab, role, modal, edit, items }) {
  const [selected, setSelected] = useState('notebook');
  const labels = { it: '信息化采购', computer: '计算机设备', notebook: '笔记本电脑', desktop: '台式机电脑' };
  const levels = { it: '采购负责类', computer: '一级品类', notebook: '二级品类', desktop: '二级品类' };
  return <><Heading title={tab.title} subtitle="采购负责类 → 一级品类 → 二级品类，使用单一父节点维护清晰归属。"><Tag>已发布 v1</Tag></Heading><div className="tree-layout"><section className="surface"><div className="surface-head"><h2>品类目录</h2><Tag>3 级</Tag></div><div className="tree-box"><Tree aria-label="三级分类树" showLine defaultExpandAll selectedKeys={[selected]} onSelect={keys => keys.length && setSelected(keys[0])} treeData={treeData.map(n => ({ ...n, selectable: true, children: n.children.map(c => ({ ...c, selectable: true })) }))} /></div></section><section className="surface"><div className="surface-head"><h2>{labels[selected]}</h2><Tag color="blue">{levels[selected]}</Tag></div><div className="detail-body"><Descriptions column={1} size="small" items={[{ key: 'path', label: '完整路径', children: ['it', 'computer', 'notebook', 'desktop'].indexOf(selected) > 1 ? `信息化采购 / 计算机设备 / ${labels[selected]}` : selected === 'computer' ? '信息化采购 / 计算机设备' : '信息化采购' }, { key: 'kind', label: '节点层级', children: levels[selected] }, { key: 'state', label: '版本状态', children: <Tag color="success">已发布</Tag> }, { key: 'count', label: '关联条目', children: `${items.filter(i => i.category === selected).length} 项` }]} /><Divider /><p className="quiet">分类归属用于定位本体条目。供应商能力与分类节点分别管理。</p>{role !== 'reader' && <Button icon={<PlusOutlined />} onClick={() => modal.info({ title: '三级树修改的后续设计', content: '此版草图展示真实 Tree 控件的选择与展开效果。节点增删及版本冲突处理将在完整设计中单独核对，当前不修改分类数据。', okText: '知道了' })}>查看分类维护说明</Button>}</div></section></div></>;
}
function OntologyPage({ tab, role, items, edit }) {
  const [view, setView] = useState('关系画布'); const [selected, setSelected] = useState('K-001');
  const nodes = [{ id: 'category', x: 45, y: 95, label: '笔记本电脑', type: '二级品类' }, { id: 'K-001', x: 305, y: 45, label: '办公笔记本电脑', type: '设备类型' }, { id: 'K-002', x: 575, y: 45, label: '设备交付验收', type: '采购要求' }, { id: 'source', x: 305, y: 175, label: '终端设备采购技术规范', type: '原始资料' }, { id: 'K-003', x: 575, y: 175, label: '台式机电脑', type: '设备类型' }];
  const readOnly = role === 'reader';
  return <><Heading title={tab.title} subtitle={role === 'platform' ? '维护通用本体基线，新发布版本仅供之后新建企业初始化。' : '用关系组织企业采购知识，每个条目均可追溯来源。'}><Tag color="success">已发布 v1</Tag>{!readOnly && <><Button icon={<LinkOutlined />} onClick={() => edit('relation')}>新增关系</Button><Button type="primary" icon={<PlusOutlined />} onClick={() => edit('knowledge')}>新增条目</Button></>}</Heading>
    <section className="surface"><div className="surface-head"><Segmented aria-label="本体展示方式" value={view} onChange={setView} options={['关系画布', '本体列表']} /><RefreshNote tab={tab} /></div>
      {view === '关系画布' && <div className="graph-area"><div className="graph-toolbar"><span className="toolbar-caption">示意关系 · 点击选择节点，在列表中编辑条目</span><Space><Tag>5 个节点</Tag><Tag>4 条连线</Tag></Space></div><svg viewBox="0 0 800 280" role="group" aria-label="本体关系示意图：品类、设备类型、采购要求与来源资料的关系"><defs><marker id={`arrow-${tab.menu}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="var(--edge)" /></marker></defs>
        <g markerEnd={`url(#arrow-${tab.menu})`}><path className="graph-edge" d="M215 126 C260 126 260 76 305 76" /><path className="graph-edge" d="M475 76 L575 76" /><path className="graph-edge" d="M390 175 L390 107" /><path className="graph-edge" d="M475 206 L575 206" /></g><g fill="var(--muted)" fontSize="10"><text x="250" y="90">归属</text><text x="510" y="65">适用</text><text x="399" y="149">依据</text><text x="507" y="195">提及</text></g>
        {nodes.map(n => <g key={n.id} className={`graph-node ${selected === n.id ? 'selected' : ''}`} transform={`translate(${n.x},${n.y})`} role="button" tabIndex={0} aria-label={`选择 ${n.label}`} onClick={() => setSelected(n.id)} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelected(n.id); } }}><rect width="170" height="62" rx="7" /><text x="14" y="24">{n.label}</text><text className="node-type" x="14" y="44">{n.type}</text></g>)}
      </svg></div>}
      <Table rowKey="id" scroll={{ x: 600 }} pagination={{ pageSize: 5, showTotal: total => `共 ${total} 个本体条目` }} dataSource={items} rowClassName={r => r.id === selected ? 'selected-item-row' : ''} columns={[
        { title: '本体条目', dataIndex: 'name', render: (v, row) => <><div className="cell-title">{v}</div><div className="cell-meta">{row.id}</div></> }, { title: '类型', dataIndex: 'kind', width: 110 }, { title: '归属品类', dataIndex: 'category', width: 110, render: v => v === 'desktop' ? '台式机电脑' : '笔记本电脑' }, { title: '状态', dataIndex: 'status', width: 100, render: v => <Tag color={v === '已发布' ? 'success' : 'processing'}>{v}</Tag> }, { title: '操作', width: 85, render: (_, row) => readOnly ? <Button type="link" size="small" onClick={() => setSelected(row.id)}>定位节点</Button> : <Button type="link" size="small" onClick={() => edit('knowledge', row)}>编辑</Button> },
      ]} /></section><div className="page-hint"><InfoCircleOutlined /> {readOnly ? '此身份仅预览已发布内容，实际权限仍由服务端校验。' : '新增和修改首先保存为待发布变更，完整版本发布后才对查询可见。'}</div>
  </>;
}
function Editor({ tab, sources, items, onChange, onSave, onClose }) {
  const [form] = Form.useForm();
  const source = sources.find(s => s.id === (tab.draft.source || 'SRC-001'));
  const knowledge = tab.kind === 'knowledge'; const relation = tab.kind === 'relation';
  return <><Heading title={tab.title} subtitle={tab.kind === 'source' ? '保留原始材料，作为后续提取、审核及追溯的依据。' : tab.kind === 'provision' ? '创建独立企业空间及首个管理员，此处仅演示表单交互。' : '补全名称、适用范围和来源证据，保存后进入待发布变更。'}><Tag color={tab.dirty ? 'processing' : 'default'}>{tab.dirty ? '未提交修改' : '编辑表单'}</Tag><Button icon={<ArrowLeftOutlined />} onClick={onClose}>取消并关闭</Button></Heading>
    <div className="form-layout"><section className="surface"><Form name={tab.id} form={form} layout="vertical" initialValues={tab.initial} onValuesChange={(_, values) => onChange(values)} onFinish={onSave} requiredMark="optional">
      <div className="form-body"><div className="form-section"><h2 className="section-title">基本信息</h2><div className="form-grid"><Form.Item name="name" label={tab.kind === 'source' ? '资料名称' : tab.kind === 'provision' ? '企业名称' : relation ? '关系名称' : '条目名称'} rules={[{ required: true, whitespace: true, message: '请填写名称' }]}><Input placeholder={relation ? '例如：适用、归属、依据' : '请输入名称'} /></Form.Item>
        {tab.kind === 'source' && <Form.Item name="format" label="资料格式"><Select options={['Markdown', '文本'].map(value => ({ value }))} /></Form.Item>}
        {knowledge && <Form.Item name="kind" label="条目类型"><Select options={['设备类型', '采购要求', '交付要求', '业务概念'].map(value => ({ value }))} /></Form.Item>}
        {relation && <><Form.Item name="subject" label="起点条目" rules={[{ required: true }]}><Select options={items.map(i => ({ value: i.id, label: i.name }))} /></Form.Item><Form.Item name="object" label="终点条目" rules={[{ required: true }]}><Select options={items.map(i => ({ value: i.id, label: i.name }))} /></Form.Item></>}
        {tab.kind === 'provision' && <><Form.Item name="company" label="企业标识" rules={[{ required: true, message: '请填写企业标识' }, { pattern: /^[A-Za-z0-9_][A-Za-z0-9_-]{0,63}$/, message: '使用字母、数字、下划线或短横线' }]}><Input placeholder="demo_company" /></Form.Item><Form.Item name="username" label="首个管理员用户名" rules={[{ required: true, whitespace: true, message: '请填写用户名' }]}><Input placeholder="仅模拟，不创建账号" /></Form.Item></>}
      </div>{knowledge && <><Form.Item name="category" label="归属二级品类" rules={[{ required: true, message: '请选择二级品类' }]}><TreeSelect treeData={treeData} treeDefaultExpandAll style={{ width: '100%' }} /></Form.Item><Form.Item name="description" label="条目描述" rules={[{ required: true, whitespace: true, message: '请填写条目描述' }]}><Input.TextArea rows={3} placeholder="清楚说明条目含义，避免将项目示例写成通用要求" /></Form.Item></>}
      {tab.kind === 'source' && <Form.Item name="content" label="资料原文" extra="草图只处理本次会话的模拟内容，请勿录入真实敏感资料。" rules={[{ required: true, whitespace: true, message: '请填写资料原文' }]}><Input.TextArea rows={9} placeholder="粘贴 Markdown 或文本内容…" /></Form.Item>}</div>
      {(knowledge || relation) && <div className="form-section"><h2 className="section-title">来源与证据</h2><Form.Item name="source" label="来源资料" rules={[{ required: true }]}><Select options={sources.map(s => ({ value: s.id, label: s.name }))} /></Form.Item><Form.Item name="evidence" label="支持这项陈述的原文" extra="保留可核对的原文，不使用模型推断代替证据。" rules={[{ required: true, whitespace: true, message: '请补充支持该陈述的原文证据' }]}><Input.TextArea rows={3} placeholder="填写直接支持条目或关系的原文" /></Form.Item>{knowledge && <Form.Item name="scope" label="适用范围"><Input placeholder="例如：特定项目、业务场景或交付阶段" /></Form.Item>}</div>}
      {tab.kind !== 'provision' && <Form.Item name="notes" label="备注"><Input.TextArea rows={2} placeholder="可选，补充审核时需要了解的信息" /></Form.Item>}
      </div><div className="form-footer"><span className="quiet" style={{ fontSize: 12 }}><InfoCircleOutlined /> {tab.kind === 'source' ? '保存后返回资料列表' : '保存变更不会直接发布本体版本'}</span><Space><Button onClick={onClose}>取消</Button><Button type="primary" htmlType="submit" icon={<SaveOutlined />}>{tab.kind === 'source' ? '保存资料' : tab.kind === 'provision' ? '模拟开通' : '保存待发布变更'}</Button></Space></div>
    </Form></section><aside className="form-context surface"><div className="context-body"><div className="context-block"><div className="context-title"><FileTextOutlined /> {tab.kind === 'source' ? '资料录入提示' : '来源原文参考'}</div>{tab.kind === 'source' ? <p className="quiet">原始资料与后续人工修订分别留存。提取首先生成候选，不自动成为已发布知识。</p> : <><div className="quiet">{source?.name}</div><blockquote className="evidence-quote">{source?.content}</blockquote><Tag>模拟资料</Tag></>}</div><div className="context-block"><div className="context-title"><AuditOutlined /> 变更流程</div>{['填写信息与来源', '人工核对与审核', '发布完整新版本'].map((step, i) => <div className="flow-step" key={step}><span className="step-number">{i + 1}</span>{step}</div>)}</div><div className="context-block"><div className="context-title">来源页面</div><span className="quiet">{tab.origin.title}</span><p className="quiet">保存成功后返回并刷新来源页，即使该页已关闭。</p></div></div></aside></div>
  </>;
}
function ReviewPage({ tab, edit, items, message }) {
  const [reviewed, setReviewed] = useState([]);
  return <><Heading title="候选审核" subtitle="逐项核对陈述与原文，保留来源、适用范围及人工修订轨迹。"><Badge count={items.length - reviewed.length} color="var(--primary)" /><Tag>模拟批次 BATCH-001</Tag></Heading><div className="review-list">{items.slice(0, 3).map(item => <article className="review-card" key={item.id}><div className="review-card-head"><h3>{item.name}</h3><Tag color={reviewed.includes(item.id) ? 'success' : 'processing'}>{reviewed.includes(item.id) ? '已核对（模拟）' : '待审核'}</Tag></div><p className="quiet">{item.description}</p><blockquote className="evidence-quote">{item.evidence}</blockquote><div className="review-card-foot"><span className="quiet" style={{ fontSize: 12 }}>来源 {item.source} · 适用范围：{item.scope}</span><Space><Button onClick={() => edit('knowledge', item, tab, true)}>修订与补证</Button><Button type="primary" disabled={reviewed.includes(item.id)} onClick={() => { setReviewed(v => [...v, item.id]); message.success('已模拟记录审核决定，尚未发布'); }}>模拟采纳</Button></Space></div></article>)}</div></>;
}
function SchemaPage({ message }) {
  const [text, setText] = useState(''); const [drafts, setDrafts] = useState([]);
  return <><Heading title="Schema 改进" subtitle="发现未映射的概念和关系，形成待审草案，经过审阅、测试及部署后再显式启用。"><Tag>当前启用 v1</Tag></Heading><div className="form-layout"><section className="surface"><div className="form-body"><h2 className="section-title">提出新的信息或关系</h2><Form layout="vertical" onFinish={() => { setDrafts(v => [...v, text]); setText(''); message.success('已生成模拟草案；当前启用版本未改变'); }}><Form.Item label="新陈述或原文"><Input.TextArea aria-label="Schema 新陈述或原文" rows={6} value={text} onChange={e => setText(e.target.value)} placeholder="输入需要扩展 Schema 的业务陈述…" /></Form.Item><Button type="primary" htmlType="submit" disabled={!text.trim()}>起草模拟待审版本</Button></Form><Divider /><h3>独立待审草案</h3>{!drafts.length ? <Empty description="暂无模拟草案" image={Empty.PRESENTED_IMAGE_SIMPLE} /> : drafts.map((d, i) => <Alert style={{ marginTop: 12 }} key={i} type="info" title={`待审草案 ${i + 1}`} description={d} />)}</div></section><aside className="surface"><div className="context-body"><h3 className="context-title"><SafetyCertificateOutlined /> 受控启用</h3><p className="quiet">草案须经过 Git 审阅、确定性生成、测试和部署，再显式切换启用版本。</p><p className="quiet">此页面不提供直接启用草案的按钮。</p></div></aside></div></>;
}
function PublishPage({ role, pending, modal }) {
  return <><Heading title={role === 'platform' ? '通用发布记录' : '发布记录'} subtitle="核对完整变更与证据后发布新版本，历史版本保持可追溯。"><Tag color="success">当前版本 v1</Tag></Heading>{role === 'platform' && <Alert style={{ marginBottom: 18 }} type="info" showIcon title="新通用版本仅用于之后新建企业的初始化" />}<div className="content-stack"><section className="surface"><div className="surface-head"><h2>待发布变更</h2><Tag color="processing">{pending.length} 项</Tag></div><Table rowKey="id" pagination={false} dataSource={pending} columns={[{ title: '变更名称', dataIndex: 'name' }, { title: '类型', dataIndex: 'kind' }, { title: '状态', dataIndex: 'status', render: v => <Tag color="processing">{v}</Tag> }]} locale={{ emptyText: <Empty description="暂无模拟变更，可以先新增一个本体条目" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }} /><div className="published-footer"><Button disabled={!pending.length} onClick={() => modal.info({ title: '核对待发布变更（模拟）', content: <><p>请核对来源、适用范围和全部差异。此草图只展示发布前的核对层，不执行真实发布。</p>{pending.map(p => <p key={p.id}><CheckCircleOutlined /> {p.kind}：{p.name}</p>)}</>, okText: '返回继续核对' })}>查看待发布差异</Button></div></section><section className="surface"><div className="surface-head"><h2>版本历史</h2></div><div className="detail-body"><Timeline items={[{ color: 'green', content: <><strong>v1 · 当前已发布</strong><p className="quiet">2026-10-21 · 初始版本（模拟）</p><Collapse size="small" items={[{ key: '1', label: '查看版本内容与审核轨迹', children: <p className="quiet">三级分类树、本体条目、来源引用及人工核对记录。完整审计轨迹由实际服务提供，此处为展示样例。</p> }]} /></> }]} /></div></section></div></>;
}
function MenuPage(props) {
  const { tab, role, edit } = props;
  if (tab.menu === 'sources') return <Sources {...props} />;
  if (tab.menu === 'tree') return <TreePage {...props} />;
  if (tab.menu === 'canvas' || tab.menu === 'generic') return <OntologyPage {...props} items={role === 'reader' ? props.items.filter(i => i.status === '已发布') : props.items} />;
  if (tab.menu === 'review') return <ReviewPage {...props} />;
  if (tab.menu === 'schema') return <SchemaPage {...props} />;
  if (tab.menu === 'publish') return <PublishPage {...props} />;
  return <><Heading title="企业开通" subtitle="从当前通用版本初始化独立企业知识空间。"><Button type="primary" icon={<PlusOutlined />} onClick={() => edit('provision')}>开通企业</Button></Heading><section className="surface"><div className="detail-body"><Alert showIcon type="info" title="平台不在此浏览或编辑企业私有知识" description="开通时复制通用本体和三级树，为企业建立独立空间及首个管理员。预览只模拟页面交互，不创建账号或保存密码。" /><div className="empty-illustration"><Empty description="点击“开通企业”体验独立功能 tab" /></div></div></section></>;
}
createRoot(document.getElementById('root')).render(<Prototype />);
