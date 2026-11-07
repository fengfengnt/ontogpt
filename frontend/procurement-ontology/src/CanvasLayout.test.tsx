import { render, screen, waitFor } from '@testing-library/react';
import type { Core, CytoscapeOptions } from 'cytoscape';
import { vi } from 'vitest';
import OntologyCanvas from './OntologyCanvas';
import { api } from './api';

let core: Core;
let layout: NonNullable<CytoscapeOptions['layout']>;
vi.mock('./api', async importOriginal => ({ ...await importOriginal<typeof import('./api')>(), api: vi.fn() }));
vi.mock('cytoscape', async importOriginal => {
  const { default: create } = await importOriginal<{ default: typeof import('cytoscape') }>();
  return { default: (options: CytoscapeOptions) => {
    layout = options.layout!;
    core = create({ ...options, styleEnabled: true, layout: { name: 'preset' },
      style: [{ selector: 'node', style: { width: 150, height: 64 } }],
    });
    vi.spyOn(core, 'width').mockReturnValue(576);
    vi.spyOn(core, 'height').mockReturnValue(420);
    core.layout(layout).run();
    return core;
  } };
});

test('connected and isolated rectangular nodes do not overlap after initial layout', async () => {
  const versions = { tree: 't1', ontology: 'o1' };
  const items = ['cost', 'requirement', 'response'].map(id => ({ id, label: id, kind: 'CollectionField' }));
  const relation = { id: 'r1', subject_id: 'requirement', object_id: 'response', predicate: 'explains' };
  vi.mocked(api).mockImplementation(async path => {
    if (path.endsWith('/tree')) return { nodes: [], category_keys: {}, versions };
    if (path.includes('/items?')) return { items, versions, count: 3 };
    if (path.includes('/items/')) return { relations: [relation] };
    return [];
  });
  let initialState = 1;
  const random = vi.spyOn(Math, 'random').mockImplementation(() =>
    ((initialState = (1664525 * initialState + 1013904223) >>> 0) / 2 ** 32));
  try {
    render(<OntologyCanvas headless onPending={() => {}} />);
    await screen.findByRole('button', { name: 'cost' });
    // The item list can render before the graph's passive effect runs.
    await waitFor(() => {
      expect(core.nodes()).toHaveLength(3);
      expect(core.edges()).toHaveLength(1);
    });
    for (let seed = 1; seed <= 20; seed++) {
      let state = seed;
      random.mockImplementation(() => ((state = (1664525 * state + 1013904223) >>> 0) / 2 ** 32));
      core.nodes().positions({ x: 0, y: 0 });
      core.layout(layout).run();
      const boxes = core.nodes().map(node => {
        const { x, y } = node.position();
        return { x1: x - 75, x2: x + 75, y1: y - 32, y2: y + 32 };
      });
      for (const box of boxes) {
        expect(Number.isFinite(box.x1) && Number.isFinite(box.y1)).toBe(true);
      }
      for (let a = 0; a < boxes.length; a++) for (let b = a + 1; b < boxes.length; b++) {
        expect(boxes[a].x2 <= boxes[b].x1 || boxes[b].x2 <= boxes[a].x1 ||
          boxes[a].y2 <= boxes[b].y1 || boxes[b].y2 <= boxes[a].y1).toBe(true);
      }
    }
  } finally { random.mockRestore(); }
});
