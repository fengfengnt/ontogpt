import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import App from './App';
import TreeEditor from './TreeEditor';
import { api } from './api';

vi.mock('./api', () => ({ api: vi.fn() }));
const versions = { tree: 't1', ontology: 'o1' };
const nodes = [
  { id: 'it', label: 'IT与通讯', level: 1, parent_id: null },
  { id: 'office', label: '办公设备', level: 2, parent_id: 'it' },
  { id: 'computer', label: '电脑', level: 3, parent_id: 'office' },
];

function identity(scope: string, role = 'company_admin') {
  vi.mocked(api).mockReset();
  vi.mocked(api).mockImplementation(async (path: string) => {
    if (path === '/v1/me') return { account_id: 'a', scope_id: scope, role };
    if (path.endsWith('/tree')) return { nodes, category_keys: { computer: 'computer' }, versions };
    if (path.includes('/ontology/items')) return { items: [], versions, count: 0 };
    if (path.includes('/schemas/active')) return { version: 'v1', item_types: [], relation_types: [], json_schema: {} };
    return [];
  });
}

test('company only sees its own workspace', async () => {
  identity('test_supplier1');
  render(<App />);
  expect(await screen.findByText('test_supplier1')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '本体画布' })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: '本体问答测试' })).not.toBeInTheDocument();
  expect(screen.queryByText('test_buyer1')).not.toBeInTheDocument();
  expect(vi.mocked(api).mock.calls.every(([path]) => !path.includes('/platform/'))).toBe(true);
});

test('platform has no company routes', async () => {
  identity('platform', 'platform_admin');
  render(<App />);
  fireEvent.click(await screen.findByRole('button', { name: '通用三级树' }));
  await waitFor(() => expect(api).toHaveBeenCalledWith('/v1/platform/tree'));
  expect(screen.queryByRole('button', { name: '本体画布' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: '资料与提取' })).not.toBeInTheDocument();
  expect(vi.mocked(api).mock.calls.every(([path]) => !path.startsWith('/v1/manage/'))).toBe(true);
});

test('tree editor rejects a fourth level', async () => {
  identity('test_buyer1');
  render(<TreeEditor prefix="/v1/manage" onPending={() => {}} />);
  fireEvent.click(await screen.findByRole('button', { name: '电脑' }));
  const add = screen.getByRole('button', { name: '新增下级' });
  expect(add).toBeDisabled();
  fireEvent.click(add);
  expect(vi.mocked(api).mock.calls.every(([, options]) => !options?.method)).toBe(true);
});

test('tree rename submits a scoped change and observed version without publishing', async () => {
  identity('test_buyer1');
  const onPending = vi.fn();
  render(<TreeEditor prefix="/v1/manage" onPending={onPending} />);
  fireEvent.click(await screen.findByRole('button', { name: '电脑' }));
  fireEvent.change(screen.getByLabelText('节点名称'), { target: { value: '电脑设备' } });
  fireEvent.click(screen.getByRole('button', { name: '保存修改' }));
  await waitFor(() => expect(onPending).toHaveBeenCalled());
  expect(api).toHaveBeenCalledWith('/v1/manage/tree', { method: 'POST', body: {
    change: { op: 'update_node', node: { id: 'computer', label: '电脑设备', level: 3, parent_id: 'office' } }, observed_version: versions,
  } });
  expect(vi.mocked(api).mock.calls.every(([path]) => !path.endsWith('/publish'))).toBe(true);
});

test('tree menu can add a procurement responsibility root', async () => {
  identity('test_buyer1');
  render(<TreeEditor prefix="/v1/manage" onPending={() => {}} />);
  fireEvent.click(await screen.findByRole('button', { name: '新增采购负责类' }));
  fireEvent.change(screen.getByLabelText('节点名称'), { target: { value: '生产物资' } });
  fireEvent.click(screen.getByRole('button', { name: '保存新节点' }));
  await waitFor(() => expect(api).toHaveBeenCalledWith('/v1/manage/tree', { method: 'POST', body: {
    change: { op: 'add_node', node: { id: expect.any(String), label: '生产物资', level: 1, parent_id: null } }, observed_version: versions,
  } }));
});

test('fixed buyer Agent entry is available only inside the buyer workspace', async () => {
  identity('test_buyer1');
  render(<App />);
  expect(await screen.findByRole('button', { name: '本体问答测试' })).toBeInTheDocument();
});
