import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import OntologyCanvas from './OntologyCanvas';
import { toChange } from './canvasChanges';
import { api, ApiError, type Item } from './api';

vi.mock('./api', async importOriginal => ({ ...(await importOriginal<typeof import('./api')>()), api: vi.fn() }));
const versions = { tree: 't1', ontology: 'o1' };
const source = { id: 's1', text: '原厂上门', simulated: true, sha256: 'a'.repeat(64) };
const item: Item = { id: 'i1', kind: 'CollectionField', label: '保修方式', description: '', category_id: 'computer', properties: {},
  scope: { project_ref: 'P1' }, source_spans: [{ revision_id: 's1', start: 0, end: 4, quote: '原厂上门' }], simulated: true, schema_version: 'v1', access_policy_ref: null };

test('canvas emits item and relation changes only', () => {
  const body = toChange(item, 'update_item', versions, ['explains']);
  expect(body).toEqual({ change: { op: 'update_item', item }, observed_version: versions });
  expect(() => toChange({ id: 'computer', level: 3 }, 'update_node', versions, [])).toThrow();
  expect(() => toChange({ id: 'r1', subject_id: 'i1', object_id: 'i2', predicate: 'deployed_but_inactive', source_spans: item.source_spans }, 'add_relation', versions, ['explains'])).toThrow('启用');
});

function data() {
  vi.mocked(api).mockReset();
  vi.mocked(api).mockImplementation(async (path, options) => {
    if (options?.method) throw new ApiError(409, 'VERSION_CHANGED', '版本已变化，请刷新后重新提交');
    if (path.endsWith('/tree')) return { nodes: [{ id: 'computer', label: '电脑', level: 3, parent_id: null }], category_keys: { computer: 'computer' }, versions };
    if (path.includes('/schemas/active')) return { version: 'v1', item_types: ['CollectionField'], relation_types: ['explains'], json_schema: {} };
    if (path.endsWith('/sources')) return [source];
    if (path.includes('/items/i1')) return { item, relations: [], sources: item.source_spans, versions };
    return { items: [item], versions, count: 1 };
  });
}

test('stale version prompts refresh and keeps edited form', async () => {
  data();
  render(<OntologyCanvas headless onPending={() => {}} />);
  fireEvent.click(await screen.findByRole('button', { name: '保修方式' }));
  fireEvent.click(screen.getByRole('button', { name: '编辑条目' }));
  fireEvent.change(screen.getByLabelText('条目名称'), { target: { value: '修改中的保修方式' } });
  fireEvent.click(screen.getByRole('button', { name: '保存到待审批次' }));
  await waitFor(() => expect(screen.getByRole('button', { name: '刷新版本以重新核对' })).toBeInTheDocument());
  expect(screen.getByLabelText('条目名称')).toHaveValue('修改中的保修方式');
  expect(screen.getByRole('button', { name: '保存到待审批次' })).toBeDisabled();
  expect(screen.queryByRole('button', { name: '新增下级' })).not.toBeInTheDocument();
  expect(screen.queryByText('编辑 LinkML')).not.toBeInTheDocument();
});
