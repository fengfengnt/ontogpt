import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { ReviewPage } from './ManagementPages';
import { api, type Batch } from './api';

vi.mock('./api', async importOriginal => ({ ...await importOriginal<typeof import('./api')>(), api: vi.fn() }));

test('stale candidate review explicitly clears old decisions against the current version', async () => {
  const versions = { tree: 't2', ontology: 'o2' };
  const candidate = { id: 'candidate1', status: 'MODEL_SUGGESTION', item: {
    id: 'item1', kind: 'CollectionField', label: '保修方式', source_spans: [], properties: {}, scope: {},
  } };
  let batch: Batch & { candidate_ids: string[] } = { id: 'batch1', kind: 'ontology', status: 'PENDING', candidate_ids: ['candidate1'],
    decisions: { candidate1: { decision: 'ACCEPTED', item: candidate.item } }, changes: [], audit: [],
    base_versions: { tree: 't1', ontology: 'o1' } };
  vi.mocked(api).mockImplementation(async (path, options) => {
    if (path.endsWith('/runs')) return [{ id: 'run1', batch_id: 'batch1', status: 'SUCCEEDED', candidate_ids: ['candidate1'], schema_version: 'v1' }];
    if (path.endsWith('/tree')) return { nodes: [], category_keys: {}, versions };
    if (path.endsWith('/restart-review')) { batch = { ...batch, decisions: {}, base_versions: versions }; return batch; }
    if (path.endsWith('/batches/batch1')) return { batch, candidates: [candidate] };
    return [];
  });
  const pending = vi.fn();
  render(<ReviewPage initialBatch="batch1" onPending={pending} />);
  fireEvent.click(await screen.findByRole('button', { name: '按当前版本重新审核（清空旧决定）' }));
  await waitFor(() => expect(pending).toHaveBeenCalledWith(expect.objectContaining({ decisions: {}, base_versions: versions })));
  expect(api).toHaveBeenCalledWith('/v1/manage/batches/batch1/restart-review', {
    method: 'POST', body: { observed_version: versions },
  });
  expect(await screen.findByText('MODEL_SUGGESTION')).toBeInTheDocument();
});
