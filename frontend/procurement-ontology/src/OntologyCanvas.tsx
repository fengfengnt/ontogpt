import { useEffect, useMemo, useRef, useState } from 'react';
import cytoscape, { type Core } from 'cytoscape';
import { api, ApiError, message, type Batch, type Item, type Relation, type Source, type Tree, type Versions } from './api';
import KnowledgeEditor, { kindLabels } from './KnowledgeEditor';
import { evidence } from './evidence';
import { toChange } from './canvasChanges';

export default function OntologyCanvas({ onPending, readOnly = false, headless = false }: {
  onPending: (batch: Batch) => void; readOnly?: boolean; headless?: boolean;
}) {
  const container = useRef<HTMLDivElement>(null);
  const graph = useRef<Core | undefined>(undefined);
  const [items, setItems] = useState<Item[]>([]);
  const [relations, setRelations] = useState<Relation[]>([]);
  const [tree, setTree] = useState<Tree>();
  const [versions, setVersions] = useState<Versions>();
  const [sources, setSources] = useState<Source[]>([]);
  const [schema, setSchema] = useState<any>();
  const [selected, setSelected] = useState('');
  const [editing, setEditing] = useState<Item | Relation | 'new-item' | 'new-relation'>();
  const [batch, setBatch] = useState<Batch>();
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('computer');
  const [error, setError] = useState('');
  const [stale, setStale] = useState(false);
  const [reloaded, setReloaded] = useState(false);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true); setError('');
    try {
      const result = await api(`/v1/ontology/items?category_key=${encodeURIComponent(category)}&q=${encodeURIComponent(query)}`);
      const detailVersions = `?tree_version=${encodeURIComponent(result.versions.tree)}&ontology_version=${encodeURIComponent(result.versions.ontology)}`;
      const [tree, details, sources, schema] = await Promise.all([
        api('/v1/manage/tree'), Promise.all(result.items.map((item: Item) => api('/v1/ontology/items/' + encodeURIComponent(item.id) + detailVersions))),
        readOnly ? Promise.resolve([]) : api('/v1/manage/sources'),
        readOnly ? Promise.resolve(undefined) : api('/v1/manage/schemas/active?category_key=' + encodeURIComponent(category)),
      ]);
      if (tree.versions.tree !== result.versions.tree || tree.versions.ontology !== result.versions.ontology) throw new ApiError(409, 'VERSION_CHANGED', '读取期间版本变化');
      setItems(result.items); setTree(tree); setSources(sources); setSchema(schema); setVersions(result.versions);
      setRelations([...new Map<string, Relation>(details.flatMap((detail: any) => detail.relations).map((relation: Relation) => [relation.id, relation])).values()]);
      if (stale) { setReloaded(true); setBatch(undefined); }
    } catch (e) { if (e instanceof ApiError && e.status === 409) setStale(true); setError(message(e)); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); }, [category]);

  const preview = useMemo(() => {
    const nodes = new Map(items.map(item => [item.id, item]));
    const edges = new Map(relations.map(relation => [relation.id, relation]));
    const statuses = new Map<string, string>();
    for (const change of batch?.changes ?? []) {
      const map = change.op.endsWith('_item') ? nodes : edges;
      const record = change.item ?? change.relation;
      const id = change.id ?? record.id;
      if (record) map.set(id, record);
      statuses.set(id, change.op.startsWith('remove_') ? 'pending-remove' : 'pending');
    }
    return { items: [...nodes.values()], relations: [...edges.values()], statuses };
  }, [items, relations, batch]);
  const selectedItem = preview.items.find(item => item.id === selected);
  const selectedRelation = preview.relations.find(relation => relation.id === selected);
  const record = selectedItem ?? selectedRelation;
  const select = (id: string) => { setSelected(id); setEditing(undefined); };

  useEffect(() => {
    if (!container.current) return;
    const style = getComputedStyle(document.documentElement);
    const css = (name: string) => style.getPropertyValue(name).trim();
    const ids = new Set(preview.items.map(item => item.id));
    const cy = cytoscape({ container: headless ? undefined : container.current, headless,
      elements: [
        ...preview.items.map(item => ({ data: { id: item.id, label: item.label + '\n' + (kindLabels[item.kind] ?? item.kind) }, classes: preview.statuses.get(item.id) ?? '' })),
        ...preview.relations.filter(relation => ids.has(relation.subject_id) && ids.has(relation.object_id))
          .map(relation => ({ data: { id: relation.id, source: relation.subject_id, target: relation.object_id, label: relation.predicate }, classes: preview.statuses.get(relation.id) ?? '' })),
      ], layout: { name: 'cose', animate: false, padding: 35 },
      style: headless ? undefined : [
        { selector: 'node', style: { 'background-color': css('--graph-node-fill'), color: css('--graph-node-text'),
          label: 'data(label)', 'text-wrap': 'wrap', 'text-max-width': '130px', 'font-family': css('--font-body'),
          'font-size': 12, width: 150, height: 64, shape: 'round-rectangle', 'text-valign': 'center' } },
        { selector: 'edge', style: { 'line-color': css('--graph-edge-stroke'), 'target-arrow-color': css('--graph-edge-stroke'),
          'target-arrow-shape': 'triangle', 'curve-style': 'bezier', width: 1.5, label: 'data(label)', 'font-size': 10, color: css('--text-muted'), 'text-background-opacity': 1, 'text-background-color': css('--surface-page') } },
        { selector: ':selected', style: { 'border-color': css('--accent'), 'border-width': 3, 'line-color': css('--accent') } },
        { selector: '.pending', style: { 'border-style': 'dashed', 'border-width': 2, 'border-color': css('--status-pending'), 'line-style': 'dashed' } },
        { selector: '.pending-remove', style: { opacity: .4, 'border-color': css('--status-error'), 'border-width': 2, 'line-style': 'dashed' } },
      ],
    });
    graph.current = cy;
    cy.on('tap', 'node,edge', event => select(event.target.id()));
    const resize = () => { cy.resize(); cy.fit(undefined, 35); };
    window.addEventListener('resize', resize);
    return () => { window.removeEventListener('resize', resize); cy.destroy(); };
  }, [preview, headless]);

  async function save(record: Item | Relation, operation: string) {
    if (!versions || stale) throw new Error('版本已变化，请刷新并重新核对');
    try {
      const body = toChange(record, operation, versions, schema?.relation_types ?? []);
      if (batch) (body.change as any).batch_id = batch.id;
      const pending = await api('/v1/manage/ontology/changes', { method: 'POST', body });
      setBatch(pending); onPending(pending); setEditing(undefined);
    } catch (e) { if (e instanceof ApiError && e.status === 409) setStale(true); setError(message(e)); throw e; }
  }
  const isRelation = editing && typeof editing === 'object' && 'subject_id' in editing;
  return <>
    <div className="toolbar">
      <label>二级品类<select value={category} disabled={!!batch || stale} onChange={e => { setCategory(e.target.value); setSelected(''); setEditing(undefined); }}>
        {tree ? Object.entries(tree.category_keys).map(([key, id]) => <option key={key} value={key}>{tree.nodes.find(node => node.id === id)?.label ?? key}</option>) : <option value="computer">电脑</option>}
      </select></label>
      <label>局部图检索<input value={query} onChange={e => setQuery(e.target.value)} placeholder="按条目名称、说明或属性过滤" /></label>
      <button disabled={loading || stale} onClick={() => load()}>检索</button><button onClick={() => graph.current?.fit(undefined, 35)}>适合视图</button>
      {!readOnly && <><button className="primary" disabled={!tree || stale} onClick={() => { setEditing('new-item'); setSelected(''); }}>新增条目</button>
        <button disabled={preview.items.length < 2 || stale} onClick={() => { setEditing('new-relation'); setSelected(''); }}>新增关系</button></>}
    </div>
    {error && <p role="alert" className="alert error">{error}</p>}
    {stale && <div className="alert error">版本已变化，本地表单仍保留。请刷新并核对新发布内容后再保存。
      <div className="toolbar"><button disabled={loading} onClick={() => load()}>刷新版本以重新核对</button>
        {reloaded && <button onClick={() => { setStale(false); setReloaded(false); setError(''); }}>确认已重新核对</button>}</div></div>}
    {versions && <p className="version">树：{versions.tree} · 本体：{versions.ontology} · {preview.items.length} 个条目 · 待发布变更不会进入问答</p>}
    <div className="canvas-grid"><section className="panel graph-panel"><div className="ontology-graph" ref={container} aria-label="企业业务本体关系画布" />
      {!preview.items.length && <p className="empty">暂无匹配的已发布条目，请先提取、审核并发布。</p>}
      <details open><summary>条目与关系列表（可使用键盘选择）</summary><div className="toolbar">
        {preview.items.map(item => <button key={item.id} onClick={() => select(item.id)}>{item.label}</button>)}
        {preview.relations.map(relation => <button key={relation.id} onClick={() => select(relation.id)}>{relation.predicate} · 关系</button>)}
      </div></details>
    </section><section className="panel"><h2>属性与来源</h2>
      {editing && tree ? <fieldset disabled={stale}>
        {editing === 'new-item' || (typeof editing === 'object' && !isRelation) ? <KnowledgeEditor
          key={typeof editing === 'object' ? editing.id : 'new'} initial={typeof editing === 'object' ? editing as Item : undefined}
          sources={sources} tree={tree} schema={schema} onCancel={() => setEditing(undefined)}
          onSave={item => save(item, editing === 'new-item' ? 'add_item' : 'update_item')} />
          : <RelationEditor key={typeof editing === 'object' ? editing.id : 'new'} initial={typeof editing === 'object' ? editing as Relation : undefined}
            items={preview.items} sources={sources} allowed={schema?.relation_types ?? []} onCancel={() => setEditing(undefined)}
            onSave={relation => save(relation, editing === 'new-relation' ? 'add_relation' : 'update_relation')} />}
      </fieldset> : record ? <>
        <h3>{selectedItem?.label ?? selectedRelation?.predicate}</h3><span className="tag">{selectedItem ? kindLabels[selectedItem.kind] ?? selectedItem.kind : '关系'}</span>
        {selectedItem?.simulated && <span className="tag">模拟</span>}{preview.statuses.has(selected) && <span className="tag pending">待发布{preview.statuses.get(selected) === 'pending-remove' ? '移除' : '修改'}</span>}
        {selectedItem && <><p>{selectedItem.description}</p><p>归属：{tree?.nodes.find(node => node.id === selectedItem.category_id)?.label}</p></>}
        <p>项目：{record.scope?.project_ref ?? '未说明'}<br />设备类型：{record.scope?.device_type ?? '未说明'}<br />阶段：{record.scope?.stage ?? '未说明'}</p>
        {record.source_spans.map((span, index) => <blockquote key={index}>{span.quote}<p className="version">{span.revision_id} [{span.start}, {span.end})</p></blockquote>)}
        {!readOnly && preview.statuses.get(selected) !== 'pending-remove' && <div className="toolbar">
          <button disabled={stale} onClick={() => setEditing(record)}>{selectedItem ? '编辑条目' : '编辑关系'}</button>
          <button className="danger" disabled={stale} onClick={() => save(record, selectedItem ? 'remove_item' : 'remove_relation').catch(() => {})}>提交移除</button>
        </div>}
      </> : <p className="muted">在画布或列表选择条目或关系。分类树在独立菜单编辑。</p>}
      {stale && reloaded && <details><summary>新发布版内容（核对用）</summary><pre>{JSON.stringify(items.find(item => item.id === (typeof editing === 'object' ? editing.id : selected)), null, 2)}</pre></details>}
    </section></div>
    {batch && <section className="panel"><h3>待发布差异</h3><ul>{batch.changes.map((change, index) => <li key={index}>
      {change.op.startsWith('remove_') ? '移除' : change.op.startsWith('add_') ? '新增' : '修改'}：{change.item?.label ?? change.relation?.predicate ?? change.id}
    </li>)}</ul><small>在“发布记录”中核对并发布，当前只读知识保持原版本。</small></section>}
  </>;
}

function RelationEditor({ initial, items, sources, allowed, onSave, onCancel }: {
  initial?: Relation; items: Item[]; sources: Source[]; allowed: string[]; onSave: (relation: Relation) => Promise<void>; onCancel: () => void;
}) {
  const [relation, setRelation] = useState<Relation>(initial ?? { id: crypto.randomUUID(), subject_id: '', object_id: '', predicate: allowed[0] ?? '', source_spans: [], scope: {} });
  const [sourceId, setSourceId] = useState(initial?.source_spans[0]?.revision_id ?? '');
  const [quote, setQuote] = useState(initial?.source_spans[0]?.quote ?? '');
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  return <form onSubmit={async event => { event.preventDefault(); setBusy(true); setError(''); try {
    const source = sources.find(source => source.id === sourceId); if (!source) throw new Error('请选择关系依据');
    await onSave({ ...relation, source_spans: [evidence(source, quote)] });
  } catch (e) { setError(message(e)); } finally { setBusy(false); } }}>
    {(['subject_id', 'object_id'] as const).map((field, index) => <label key={field}>{index ? '关系客体' : '关系主体'}<select required value={relation[field]} onChange={e => setRelation({ ...relation, [field]: e.target.value })}>
      <option value="">请选择</option>{items.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}
    </select></label>)}
    <label>当前启用的关系类型<select required value={relation.predicate} onChange={e => setRelation({ ...relation, predicate: e.target.value })}>{allowed.map(type => <option key={type}>{type}</option>)}</select></label>
    {['project_ref', 'device_type', 'stage'].map(key => <label key={key}>{{ project_ref: '项目编号', device_type: '设备类型', stage: '阶段' }[key]}<input value={relation.scope[key] ?? ''} onChange={e => setRelation({ ...relation, scope: { ...relation.scope, [key]: e.target.value || null } })} /></label>)}
    <label>关系来源<select required value={sourceId} onChange={e => setSourceId(e.target.value)}><option value="">请选择</option>{sources.map(source => <option key={source.id} value={source.id}>{source.text.slice(0, 35)}</option>)}</select></label>
    <label>关系原文摘录<textarea required value={quote} onChange={e => setQuote(e.target.value)} /></label>
    {error && <p role="alert" className="alert error">{error}</p>}<div className="toolbar"><button className="primary" disabled={busy}>保存到待审批次</button><button type="button" onClick={onCancel}>取消</button></div>
  </form>;
}
