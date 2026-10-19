import { fireEvent, render, screen } from '@testing-library/react';
import { vi } from 'vitest';
import AgentPage from './AgentPage';
import { api } from './api';

vi.mock('./api', () => ({ api: vi.fn() }));

test('Agent page displays actual tool evidence and versions', async () => {
  vi.mocked(api).mockResolvedValue({ answer: '该项目采用原厂上门服务。', versions: { tree: 'tree-v1', ontology: 'ontology-v2' }, citations: [
    { item_id: 'warranty', label: '保修方式', simulated: true, scope: { project_ref: 'P1' }, source_spans: [{ quote: '原厂上门', revision_id: 's1', start: 0, end: 4 }] },
  ] });
  render(<AgentPage />);
  fireEvent.change(screen.getByLabelText('问题'), { target: { value: '保修方式是什么？' } });
  fireEvent.click(screen.getByRole('button', { name: '基于已发布本体回答' }));
  expect(await screen.findByText('该项目采用原厂上门服务。')).toBeInTheDocument();
  expect(screen.getByText('原厂上门')).toBeInTheDocument();
  expect(screen.getByText(/ontology-v2/)).toBeInTheDocument();
  expect(api).toHaveBeenCalledWith('/v1/agent/questions', { method: 'POST', body: { question: '保修方式是什么？' } });
});
