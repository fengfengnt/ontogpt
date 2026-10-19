import { useEffect, useState } from 'react';
import { api, message, type Batch, type Item, type Relation, type Source, type Tree } from './api';
import KnowledgeEditor from './KnowledgeEditor';
import { evidence } from './evidence';

export default function PlatformEditor({ onPending }: { onPending: (batch: Batch) => void }) {
  const [items, setItems] = useState<Item[]>([]);
  const [tree, setTree] = useState<Tree>();
  const [sources, setSources] = useState<Source[]>([]);
  const [edit, setEdit] = useState<Item | 'new'>();
  const [text, setText] = useState('');
  const [simulated, setSimulated] = useState(true);
  const [error, setError] = useState('');
  const [relations, setRelations] = useState<Relation[]>([]);
  const [subject, setSubject] = useState('');
  const [object, setObject] = useState('');
  const [sourceId, setSourceId] = useState('');
  const [quote, setQuote] = useState('');
  useEffect(() => { Promise.all([api('/v1/platform/tree'), api('/v1/platform/ontology/items?category_key=computer'), api('/v1/platform/sources')])
    .then(async ([tree, result, sources]) => {
      setTree(tree); setItems(result.items); setSources(sources);
      const details = await Promise.all(result.items.map((item: Item) => api('/v1/platform/ontology/items/' + encodeURIComponent(item.id))));
      setRelations([...new Map<string, Relation>(details.flatMap((detail: any) => detail.relations).map((relation: Relation) => [relation.id, relation])).values()]);
    }).catch(e => setError(message(e))); }, []);
  async function change(change: any) {
    if (!tree) return;
    onPending(await api('/v1/platform/ontology/changes', { method: 'POST', body: { change, observed_version: tree.versions } }));
  }
  return <>
    <p className="alert">通用本体和通用树的新版本用于之后新建的企业；已建企业不会自动同步。</p>
    {error && <p role="alert" className="alert error">{error}</p>}
    <div className="two-col"><section className="panel"><h2>通用条目</h2>
      <button className="primary" disabled={!tree} onClick={() => setEdit('new')}>新增通用条目</button>
      {items.map(item => <article className="record" key={item.id}><h3>{item.label}</h3><p>{item.description}</p>
        <button onClick={() => setEdit(item)}>编辑属性</button> <button className="danger" onClick={() => change({ op: 'remove_item', id: item.id }).catch(e => setError(message(e)))}>提交移除</button>
      </article>)}
      {!items.length && <p className="empty">暂无已发布通用条目</p>}
      <hr /><h3>通用关系</h3>
      {relations.map(relation => <div className="record" key={relation.id}>{items.find(i => i.id === relation.subject_id)?.label} → {items.find(i => i.id === relation.object_id)?.label}
        <button className="danger" onClick={() => change({ op: 'remove_relation', id: relation.id }).catch(e => setError(message(e)))}>移除关系</button></div>)}
      <label>关系主体<select value={subject} onChange={e => setSubject(e.target.value)}><option value="">请选择</option>{items.map(i => <option key={i.id} value={i.id}>{i.label}</option>)}</select></label>
      <label>关系客体<select value={object} onChange={e => setObject(e.target.value)}><option value="">请选择</option>{items.map(i => <option key={i.id} value={i.id}>{i.label}</option>)}</select></label>
      <span className="tag">related_to</span>
      <label>关系来源<select value={sourceId} onChange={e => setSourceId(e.target.value)}><option value="">请选择</option>{sources.map(s => <option key={s.id} value={s.id}>{s.text.slice(0, 30)}</option>)}</select></label>
      <label>关系摘录<textarea value={quote} onChange={e => setQuote(e.target.value)} /></label>
      <button disabled={!subject || !object || !sourceId || !quote} onClick={() => {
        try { const source = sources.find(s => s.id === sourceId)!;
          change({ op: 'add_relation', relation: { id: crypto.randomUUID(), subject_id: subject, object_id: object, predicate: 'related_to', scope: {}, source_spans: [evidence(source, quote)] } }).catch(e => setError(message(e)));
        } catch (e) { setError(message(e)); }
      }}>保存新关系</button>
    </section><section className="panel"><h2>{edit ? '条目属性' : '通用来源'}</h2>
      {edit && tree ? <KnowledgeEditor key={edit === 'new' ? 'new' : edit.id} initial={edit === 'new' ? undefined : edit} sources={sources} tree={tree}
        onSave={item => change({ op: edit === 'new' ? 'add_item' : 'update_item', item })} onCancel={() => setEdit(undefined)} /> : <>
        <p className="muted">新增通用知识也需要依据，先保存管理员陈述或材料原文。</p>
        <label>来源内容<textarea value={text} onChange={e => setText(e.target.value)} /></label>
        <label className="check"><input type="checkbox" checked={simulated} onChange={e => setSimulated(e.target.checked)} />模拟材料</label>
        <button disabled={!text.trim()} onClick={async () => { try {
          const source = await api('/v1/platform/sources', { method: 'POST', body: { text, simulated } });
          setSources([...sources, source]); setText('');
        } catch (e) { setError(message(e)); } }}>保存通用来源</button>
        <p className="muted">已保存 {sources.length} 份来源修订</p>
      </>}
    </section></div>
  </>;
}
