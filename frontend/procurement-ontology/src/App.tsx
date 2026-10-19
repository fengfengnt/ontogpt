import { useEffect, useState } from 'react';
import { api, message, type Batch, type Identity } from './api';
import TreeEditor from './TreeEditor';
import PlatformEditor from './PlatformEditor';
import { PublishPage, ReviewPage, SchemaPage, SourcesPage } from './ManagementPages';

export default function App() {
  const [identity, setIdentity] = useState<Identity | null>();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState('');
  const [batchId, setBatchId] = useState<string>();
  const [pending, setPending] = useState<Batch>();
  const [refresh, setRefresh] = useState(0);
  useEffect(() => { api('/v1/me').then(setIdentity).catch(() => setIdentity(null)); }, []);
  if (identity === undefined) return <p className="empty" role="status">加载工作区…</p>;
  if (!identity) return <form className="panel login" onSubmit={async event => { event.preventDefault(); setBusy(true); setError(''); try {
    setIdentity(await api('/v1/session', { method: 'POST', body: { username, password } })); setPassword(''); setTab('');
  } catch (e) { setError(message(e)); } finally { setBusy(false); } }}>
    <span className="eyebrow">采购知识工作台</span><h1>让知识有据可查</h1><p className="muted">登录企业或平台管理员账号</p>
    <label>用户名<input required autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} /></label>
    <label>密码<input required type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} /></label>
    {error && <p role="alert" className="alert error">{error}</p>}<button className="primary" disabled={busy}>{busy ? '登录中…' : '进入工作区'}</button>
  </form>;
  const platform = identity.scope_id === 'platform';
  const reader = identity.role === 'reader';
  const prefix = platform ? '/v1/platform' : '/v1/manage';
  const menus = platform ? [['generic', '通用本体'], ['tree', '通用三级树'], ['publish', '通用发布记录'], ['provision', '企业开通']]
    : reader ? [['canvas', '本体画布'], ['tree', '三级分类树']] : [['sources', '资料与提取'], ['review', '候选审核'], ['canvas', '本体画布'], ['tree', '三级分类树'], ['schema', 'Schema 改进'], ['publish', '发布记录']];
  const selected = tab || menus[0][0];
  const title = menus.find(([key]) => key === selected)?.[1] ?? '工作区';
  function onPending(batch: Batch) { setPending(batch); }
  return <div className="workspace"><aside className="sidebar"><div className="brand"><span className="brand-mark">知</span><div>采购知识工作台<small>KNOWLEDGE STUDIO</small></div></div>
    <nav aria-label="工作区菜单">{menus.map(([key, label]) => <button key={key} aria-current={selected === key ? 'page' : undefined} onClick={() => { setTab(key); setError(''); }}>{label}</button>)}</nav>
    <div className="identity"><div><strong>{identity.scope_id}</strong><small style={{ display: 'block' }}>{platform ? '平台管理员' : reader ? '企业查询账号' : '企业管理员'}</small></div>
      <button onClick={async () => { try { await api('/v1/session', { method: 'DELETE' }); setIdentity(null); setPending(undefined); setBatchId(undefined); } catch (e) { setError(message(e)); } }}>退出登录</button></div>
  </aside><main className="main"><header className="page-header"><div><span className="eyebrow">{platform ? '通用模板管理' : '企业独立知识空间'} / 电脑(台式机/笔记本)</span><h1>{title}</h1></div>
    <span className="tag">{platform ? '仅用于新企业初始化' : '只读已发布 · 修改先待审'}</span></header>
    <div className="content">
      {error && <p role="alert" className="alert error">{error}</p>}
      {pending && selected !== 'publish' && <div className="alert">变更已保存，尚未发布。 <button onClick={() => setTab('publish')}>查看待发布差异</button></div>}
      <div key={selected + refresh}>
        {selected === 'sources' && !platform && !reader && <SourcesPage onReview={id => { setBatchId(id); setTab('review'); }} />}
        {selected === 'review' && !platform && !reader && <ReviewPage initialBatch={batchId} onPending={onPending} />}
        {selected === 'tree' && <TreeEditor prefix={prefix} onPending={onPending} readOnly={reader} />}
        {selected === 'generic' && platform && <PlatformEditor onPending={onPending} />}
        {selected === 'canvas' && !platform && <PublishedList />}
        {selected === 'schema' && !platform && !reader && <SchemaPage company={identity.scope_id} />}
        {selected === 'publish' && !reader && <PublishPage prefix={prefix} onPublished={() => { setPending(undefined); setRefresh(value => value + 1); }} />}
        {selected === 'provision' && platform && <ProvisionPage />}
      </div>
    </div></main></div>;
}

function PublishedList() {
  const [items, setItems] = useState<any[]>([]);
  const [error, setError] = useState('');
  useEffect(() => { api('/v1/ontology/items?category_key=computer').then(result => setItems(result.items)).catch(e => setError(message(e))); }, []);
  return <section className="panel"><h2>当前已发布知识</h2>{error && <p role="alert">{error}</p>}
    {items.map(item => <article className="record" key={item.id}><h3>{item.label}</h3><p>{item.description}</p></article>)}
    {!items.length && <p className="empty">暂无已发布知识，请先完成资料提取、审核和发布。</p>}
  </section>;
}

function ProvisionPage() {
  const [company, setCompany] = useState(''); const [username, setUsername] = useState(''); const [password, setPassword] = useState('');
  const [result, setResult] = useState(''); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  return <form className="panel" onSubmit={async event => { event.preventDefault(); setBusy(true); setError(''); try {
    const result = await api('/v1/platform/companies', { method: 'POST', body: { company_id: company, username, password } });
    setResult(result.company_id + ' · ' + result.status); setPassword('');
  } catch (e) { setError(message(e)); } finally { setBusy(false); } }}><h2>初始化独立企业空间</h2>
    <p className="muted">复制当前通用本体和三级树，创建企业首个管理员。此入口不提供企业知识浏览或编辑。</p>
    <label>企业标识<input required pattern="[A-Za-z0-9_][A-Za-z0-9_-]{0,63}" value={company} onChange={e => setCompany(e.target.value)} /></label>
    <label>首个管理员用户名<input required value={username} onChange={e => setUsername(e.target.value)} autoComplete="off" /></label>
    <label>初始密码<input required minLength={12} type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete="new-password" /></label>
    {error && <p role="alert" className="alert error">{error}</p>}{result && <p role="status" className="alert">{result}</p>}
    <button className="primary" disabled={busy}>{busy ? '初始化中…' : '创建企业实例'}</button>
  </form>;
}
