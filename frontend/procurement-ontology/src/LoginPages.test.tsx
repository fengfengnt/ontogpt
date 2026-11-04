import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, expect, test, vi } from 'vitest';
import App from './App';
import { api } from './api';

vi.mock('./api', () => ({ api: vi.fn(), message: (error: unknown) => error instanceof Error ? error.message : '操作失败' }));

beforeEach(() => {
  window.history.replaceState(null, '', '/');
  vi.mocked(api).mockReset();
});

test('anonymous root offers SSO and a separate password URL', async () => {
  vi.mocked(api).mockImplementation(async path => {
    if (path === '/v1/me') throw new Error('需要登录');
    if (path === '/v1/auth/sso/config') return { enabled: true };
    return [];
  });
  render(<App />);
  expect(await screen.findByRole('link', { name: 'SSO 登录' })).toHaveAttribute('href', '/v1/auth/sso/start');
  expect(screen.getByRole('link', { name: '用户名密码登录' })).toHaveAttribute('href', '/login/password');
  expect(screen.queryByLabelText('密码')).not.toBeInTheDocument();
});

test('unconfigured SSO still exposes password login', async () => {
  vi.mocked(api).mockImplementation(async path => {
    if (path === '/v1/me') throw new Error('需要登录');
    return { enabled: false };
  });
  render(<App />);
  expect(await screen.findByText('SSO 尚未配置')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: '用户名密码登录' })).toHaveAttribute('href', '/login/password');
});

test('password URL accepts an existing enterprise account and returns to root', async () => {
  window.history.replaceState(null, '', '/login/password');
  vi.mocked(api).mockImplementation(async (path, options) => {
    if (path === '/v1/me') throw new Error('需要登录');
    if (path === '/v1/session') {
      expect(options?.body).toEqual({ username: 'reader', password: 'synthetic-password' });
      return { account_id: 'a', scope_id: 'company', role: 'reader' };
    }
    if (path.endsWith('/tree')) return { nodes: [], versions: {}, category_keys: {} };
    return { items: [], versions: {} };
  });
  render(<App />);
  fireEvent.change(await screen.findByLabelText('用户名'), { target: { value: 'reader' } });
  fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'synthetic-password' } });
  fireEvent.click(screen.getByRole('button', { name: '进入工作区' }));
  expect(await screen.findByText('企业查询账号')).toBeInTheDocument();
  expect(window.location.pathname).toBe('/');
});

test('pending user sees no enterprise menu and can refresh assignment or log out', async () => {
  vi.mocked(api).mockImplementation(async path => {
    if (path === '/v1/me') return { status: 'PENDING_ASSIGNMENT', account_id: null, scope_id: null, role: null, preferred_username: 'SSO user' };
    if (path === '/v1/session/activate') throw new Error('尚未分配企业，请等待超级管理员处理');
    if (path === '/v1/auth/sso/config') return { enabled: true };
    return {};
  });
  render(<App />);
  expect(await screen.findByText('等待分配企业空间')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: '本体画布' })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: '刷新分配状态' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('尚未分配企业');
  fireEvent.click(screen.getByRole('button', { name: '退出登录' }));
  expect(await screen.findByRole('link', { name: 'SSO 登录' })).toBeInTheDocument();
});

test('platform assigns a pending SSO user with fixed company administrator role', async () => {
  let assigned = false;
  vi.mocked(api).mockImplementation(async (path, options) => {
    if (path === '/v1/me') return { account_id: 'p', scope_id: 'platform', role: 'platform_admin' };
    if (path === '/v1/platform/sso-users') return [{ id: 'external-1', subject: 'member:1:7', preferred_username: 'New user', company_id: assigned ? 'buyer' : null }];
    if (path === '/v1/platform/companies') return ['buyer'];
    if (path === '/v1/platform/sso-users/external-1/assignment') {
      expect(options?.body).toEqual({ company_id: 'buyer' });
      assigned = true;
      return { account_id: 'new', scope_id: 'buyer', role: 'company_admin' };
    }
    if (path.endsWith('/sources')) return [];
    return { items: [], versions: {}, nodes: [] };
  });
  render(<App />);
  fireEvent.click(await screen.findByRole('button', { name: 'SSO 用户分配' }));
  fireEvent.change(await screen.findByLabelText('New user 的企业空间'), { target: { value: 'buyer' } });
  expect(screen.getByText('角色：企业管理员')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: '分配企业' }));
  expect(await screen.findByText('已分配：buyer')).toBeInTheDocument();
});

test('SSO user list failure remains visible and can be retried', async () => {
  vi.mocked(api).mockImplementation(async path => {
    if (path === '/v1/me') return { account_id: 'p', scope_id: 'platform', role: 'platform_admin' };
    if (path === '/v1/platform/sso-users') throw new Error('列表加载失败');
    if (path.endsWith('/sources')) return [];
    return { items: [], versions: {}, nodes: [] };
  });
  render(<App />);
  fireEvent.click(await screen.findByRole('button', { name: 'SSO 用户分配' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('列表加载失败');
  expect(screen.getByRole('button', { name: '刷新列表' })).toBeEnabled();
});
