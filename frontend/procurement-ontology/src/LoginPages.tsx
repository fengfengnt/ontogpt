import { useEffect, useState } from 'react';
import { api, message, type Identity, type PendingIdentity } from './api';

export function LoginPage({ onLogin }: { onLogin: (identity: Identity) => void }) {
  const passwordMode = window.location.pathname === '/login/password';
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [enabled, setEnabled] = useState<boolean>();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!passwordMode) api('/v1/auth/sso/config').then(result => setEnabled(result.enabled)).catch(e => setError(message(e)));
  }, [passwordMode]);
  if (!passwordMode) return <section className="panel login">
    <span className="eyebrow">采购知识工作台</span><h1>让知识有据可查</h1>
    <p className="muted">通过统一身份平台登录，首次登录后由超级管理员分配企业空间。</p>
    {enabled === true ? <p><a className="primary" href="/v1/auth/sso/start">SSO 登录</a></p>
      : <p role="status">{enabled === false ? 'SSO 尚未配置' : error ? 'SSO 暂不可用' : '检查登录配置…'}</p>}
    {error && <p role="alert" className="alert error">{error}</p>}
    <p><a href="/login/password">用户名密码登录</a></p>
  </section>;
  return <form className="panel login" onSubmit={async event => {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const identity = await api('/v1/session', { method: 'POST', body: { username, password } });
      setPassword(''); window.history.replaceState(null, '', '/'); onLogin(identity);
    } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }}>
    <span className="eyebrow">采购知识工作台</span><h1>用户名密码登录</h1>
    <p className="muted">使用已有企业账号或平台管理员账号登录</p>
    <label>用户名<input required autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} /></label>
    <label>密码<input required type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} /></label>
    {error && <p role="alert" className="alert error">{error}</p>}
    <button className="primary" disabled={busy}>{busy ? '登录中…' : '进入工作区'}</button>
    <p><a href="/">返回 SSO 登录</a></p>
  </form>;
}

export function PendingPage({ identity, onLogin, onLogout }: {
  identity: PendingIdentity; onLogin: (identity: Identity) => void; onLogout: () => void;
}) {
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function refresh() {
    setBusy(true); setError('');
    try { onLogin(await api('/v1/session/activate', { method: 'POST' })); }
    catch (e) { setError(message(e)); } finally { setBusy(false); }
  }
  async function logout() {
    setBusy(true); setError('');
    try { await api('/v1/session', { method: 'DELETE' }); onLogout(); }
    catch (e) { setError(message(e)); } finally { setBusy(false); }
  }
  return <section className="panel login">
    <span className="eyebrow">采购知识工作台</span><h1>等待分配企业空间</h1>
    <p>{identity.preferred_username || 'SSO 用户'}，你已完成身份认证。</p>
    <p className="muted">请联系超级管理员分配企业空间。分配后，你将以企业管理员身份进入对应工作区。</p>
    {error && <p role="alert" className="alert error">{error}</p>}
    <button className="primary" disabled={busy} onClick={refresh}>{busy ? '处理中…' : '刷新分配状态'}</button>{' '}
    <button disabled={busy} onClick={logout}>退出登录</button>
  </section>;
}

type SSOUser = { id: string; subject: string; preferred_username: string; company_id: string | null };

export function SSOAssignments() {
  const [users, setUsers] = useState<SSOUser[]>([]);
  const [companies, setCompanies] = useState<string[]>([]);
  const [selected, setSelected] = useState<Record<string, string>>({});
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function load() {
    const [users, companies] = await Promise.all([api('/v1/platform/sso-users'), api('/v1/platform/companies')]);
    setUsers(users); setCompanies(companies);
  }
  async function refresh() {
    setBusy(true); setError('');
    try { await load(); } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }
  useEffect(() => { void refresh(); }, []);
  return <section className="panel"><h2>SSO 用户分配</h2>
    <p className="muted">仅显示已通过 SSO 登录的用户。分配角色固定为企业管理员，已有本地账号不会自动合并。</p>
    <button disabled={busy} onClick={refresh}>刷新列表</button>
    {error && <p role="alert" className="alert error">{error}</p>}
    {busy && <p role="status">处理中…</p>}
    {!busy && !error && users.length === 0 && <p className="empty">暂无 SSO 用户</p>}
    {!busy && users.some(user => !user.company_id) && companies.length === 0 && <p className="alert">请先通过“企业开通”创建企业空间。</p>}
    {users.map(user => <form key={user.id} className="panel" onSubmit={async event => {
      event.preventDefault(); setBusy(true); setError('');
      try {
        await api('/v1/platform/sso-users/' + encodeURIComponent(user.id) + '/assignment', { method: 'POST', body: { company_id: selected[user.id] } });
        await load();
      } catch (e) { setError(message(e)); } finally { setBusy(false); }
    }}>
      <h3>{user.preferred_username || user.subject}</h3><p className="muted">{user.subject}</p>
      {user.company_id ? <p role="status">已分配：{user.company_id}</p> : <>
        <label>{user.preferred_username || user.subject} 的企业空间<select required value={selected[user.id] || ''}
          disabled={busy} onChange={event => setSelected({ ...selected, [user.id]: event.target.value })}>
          <option value="">选择企业空间</option>{companies.map(company => <option key={company} value={company}>{company}</option>)}
        </select></label>
        <p>角色：企业管理员</p><button className="primary" disabled={busy || !selected[user.id]}>分配企业</button>
      </>}
    </form>)}
  </section>;
}
