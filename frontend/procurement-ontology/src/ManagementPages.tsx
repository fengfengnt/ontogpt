import { useEffect, useState } from 'react';
import { ApiError, api, message, type Batch, type Item, type Source, type Tree } from './api';
import KnowledgeEditor, { kindLabels } from './KnowledgeEditor';

export function SourcesPage({ onReview }: { onReview: (id: string) => void }) {
  const [text, setText] = useState('');
  const [simulated, setSimulated] = useState(true);
  const [runs, setRuns] = useState<any[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const refresh = () => Promise.all([api('/v1/manage/sources'), api('/v1/manage/runs')]).then(([s, r]) => { setSources(s); setRuns(r); });
  useEffect(() => { refresh().catch(e => setError(message(e))); }, []);
  async function extract(source: Source) {
    setBusy(true); setError('');
    try {
      const run = await api(`/v1/manage/sources/${source.id}/extract`, { method: 'POST', body: { category_key: 'computer' } });
      await refresh();
      if (run.status === 'FAILED') setError('提取失败，原文已保存。请检查模型连接后重试。诊断：' + run.error_code);
      else onReview(run.batch_id);
    } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }
  return <div className="two-col"><section className="panel"><h2>从材料建立候选</h2>
    <p className="muted">模型按本企业已启用的提取规范处理原文。候选经过人工审核和发布后才能用于问答。</p>
    <label>选择文本文件<input type="file" accept=".md,.txt,text/plain,text/markdown" onChange={async e => {
      const file = e.target.files?.[0]; if (file) { try { setText(await file.text()); } catch (e) { setError(message(e)); } }
    }} /></label>
    <label>材料原文<textarea className="source-text" value={text} onChange={e => setText(e.target.value)} placeholder="粘贴需求、投标材料或企业管理员的新陈述" /></label>
    <label className="check"><input type="checkbox" checked={simulated} onChange={e => setSimulated(e.target.checked)} />这是模拟材料</label>
    {error && <p role="alert" className="alert error">{error}</p>}
    <button className="primary" disabled={busy || !text.trim()} onClick={async () => {
      setBusy(true); setError('');
      try { const source = await api('/v1/manage/sources', { method: 'POST', body: { text, simulated } }); await extract(source); }
      catch (e) { setError(message(e)); } finally { setBusy(false); }
    }}>{busy ? '正在保存与提取…' : '保存原文并提取候选'}</button>
    <p className="version">模拟标记、原文摘要和操作者由服务保存。材料中的指令不授予系统操作权限。</p>
  </section><section className="panel"><h2>提取记录 <span className="tag">{runs.length}</span></h2>
    {runs.map(run => <article className="record" key={run.id}>
      <span className="tag">{run.status}</span><span className="tag">{run.schema_version}</span>
      <p className="version">{run.id}</p><p>{run.candidate_ids.length} 个候选 · {run.unmapped_suggestions.length} 个未映射建议</p>
      {run.status === 'SUCCEEDED' ? <button onClick={() => onReview(run.batch_id)}>审核本次候选</button>
        : run.status === 'FAILED' && <button disabled={busy} onClick={() => { const source = sources.find(s => s.id === run.revision_id); if (source) extract(source); }}>重试提取</button>}
    </article>)}
    {!runs.length && <p className="empty">暂无提取记录</p>}
    <hr /><h3>已保存原文 <span className="tag">{sources.length}</span></h3>
    {sources.map(source => <details key={source.id}><summary>{source.simulated ? '模拟 · ' : ''}{source.text.slice(0, 35)}</summary>
      <blockquote>{source.text}</blockquote><p className="version">{source.sha256}</p></details>)}
  </section></div>;
}

export function ReviewPage({ initialBatch, onPending }: { initialBatch?: string; onPending: (batch: Batch) => void }) {
  const [runs, setRuns] = useState<any[]>([]);
  const [batchId, setBatchId] = useState(initialBatch ?? '');
  const [result, setResult] = useState<any>();
  const [sources, setSources] = useState<Source[]>([]);
  const [tree, setTree] = useState<Tree>();
  const [schema, setSchema] = useState<any>();
  const [editing, setEditing] = useState<any>();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [conflict, setConflict] = useState(false);
  useEffect(() => { Promise.all([api('/v1/manage/runs'), api('/v1/manage/sources'), api('/v1/manage/tree'), api('/v1/manage/schemas/active')])
    .then(([r, s, t, schema]) => { setRuns(r.filter((run: any) => run.status === 'SUCCEEDED')); setSources(s); setTree(t); setSchema(schema); })
    .catch(e => setError(message(e))); }, []);
  useEffect(() => { if (batchId) api('/v1/manage/batches/' + batchId).then(setResult).catch(e => setError(message(e))); }, [batchId]);
  async function review(candidate: any, decision: string, corrected?: Item) {
    setBusy(true); setError('');
    try {
      const batch = await api(`/v1/manage/batches/${batchId}/reviews`, { method: 'POST', body: { candidate_id: candidate.id, decision, ...(corrected ? { corrected } : {}) } });
      setResult(await api('/v1/manage/batches/' + batchId)); setEditing(undefined); onPending(batch);
    } catch (e) { setError(message(e)); if (e instanceof ApiError && e.status === 409) setConflict(true); throw e; } finally { setBusy(false); }
  }
  const stale = result?.batch?.status === 'PENDING' && (conflict || (tree &&
    (tree.versions.tree !== result.batch.base_versions.tree || tree.versions.ontology !== result.batch.base_versions.ontology)));
  return <>
    <label>选择提取批次<select value={batchId} onChange={e => { setBatchId(e.target.value); setEditing(undefined); setConflict(false); }}>
      <option value="">请选择</option>{runs.map(run => <option key={run.id} value={run.batch_id}>{run.schema_version} · {run.id.slice(-12)} · {run.candidate_ids.length} 个候选</option>)}
    </select></label>
    {error && <p role="alert" className="alert error">{error}</p>}
    {stale && <section className="panel"><p>本批次基础版本已过期。重新审核将清空旧决定，保留历史审计；请逐条重新核对后发布。</p>
      <button disabled={busy} onClick={async () => {
        setBusy(true); setError('');
        try {
          const current = await api('/v1/manage/tree');
          const batch = await api(`/v1/manage/batches/${batchId}/restart-review`, { method: 'POST', body: { observed_version: current.versions } });
          setTree(current); setResult(await api('/v1/manage/batches/' + batchId)); setEditing(undefined); setConflict(false); onPending(batch);
        } catch (e) { setError(message(e)); } finally { setBusy(false); }
      }}>按当前版本重新审核（清空旧决定）</button>
    </section>}
    <div className="two-col"><section className="panel"><h2>候选审核</h2>
      <p className="muted">采纳表示完成本条人工核对，发布仍需独立执行。无法定位原文的建议须先补证。</p>
      {result?.candidates.map((candidate: any) => {
        const decision = result.batch?.decisions[candidate.id];
        const item = decision?.item ?? candidate.item;
        return <article className="record" key={candidate.id}><h3>{item.label ?? item.predicate}</h3>
          <span className="tag pending">{decision?.decision ?? candidate.status}</span><span className="tag">{kindLabels[item.kind] ?? item.kind ?? '关系'}</span>
          {item.simulated && <span className="tag">模拟</span>}<p>{item.description}</p>
          {item.scope?.project_ref && <p>项目：{item.scope.project_ref} · {item.scope.stage ?? '阶段未说明'}</p>}
          {(item.source_spans ?? []).map((span: any, index: number) => <blockquote key={index}>{span.quote}</blockquote>)}
          {!item.source_spans.length && <blockquote>{candidate.proposed_evidence_quote ?? '尚无可定位证据'}</blockquote>}
          {item.properties && <dl>{Object.entries(item.properties).filter(([, value]) => value != null).map(([key, value]) => <div key={key}><dt className="muted">{key}</dt><dd>{String(value)}</dd></div>)}</dl>}
          {item.subject_id && <p className="version">{item.subject_id} → {item.object_id}</p>}
          {result.batch?.status !== 'PUBLISHED' && <div className="toolbar">
            <button disabled={busy || stale || !item.source_spans.length} onClick={() => review(candidate, 'ACCEPTED').catch(() => {})}>采纳</button>
            {item.kind && <button disabled={busy || stale} onClick={() => setEditing({ ...candidate, item })}>修订与补证</button>}
            <button className="danger" disabled={busy || stale} onClick={() => review(candidate, 'REJECTED').catch(() => {})}>拒绝</button>
          </div>}
        </article>;
      })}
      {(!result || !result.candidates.length) && <p className="empty">选择提取批次后开始审核</p>}
    </section><section className="panel"><h2>核对来源与适用范围</h2>
      {editing && tree ? <KnowledgeEditor key={editing.id} initial={editing.item} sources={sources} tree={tree} schema={schema}
        onSave={item => review(editing, 'ACCEPTED', item)} onCancel={() => setEditing(undefined)} />
        : <p className="muted">检查原文是否支持陈述，并保留设备类型、项目和阶段。项目示例不能作为品类的永久默认要求。</p>}
    </section></div>
  </>;
}

export function PublishPage({ prefix, onPublished }: { prefix: string; onPublished: () => void }) {
  const [batches, setBatches] = useState<Batch[]>([]);
  const [confirmed, setConfirmed] = useState<Record<string, boolean>>({});
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const refresh = () => api(prefix + '/batches').then(setBatches);
  useEffect(() => { refresh().catch(e => setError(message(e))); }, [prefix]);
  return <section className="panel"><h2>变更与发布记录</h2>
    {prefix.includes('/platform') && <p className="alert">新通用版本只用于之后新建的企业。</p>}
    {error && <p role="alert" className="alert error">{error}</p>}
    {batches.map(batch => <article className="record" key={batch.id}><h3>{batch.kind === 'tree' ? '三级树变更' : '本体变更'}</h3>
      <span className="tag">{batch.status === 'PUBLISHED' ? '已发布' : '待发布'}</span><p className="version">{batch.id}</p>
      <p>{batch.changes.length} 项人工修改 · {Object.keys(batch.decisions).length} 项候选审核</p>
      <details><summary>核对差异、基础版本与操作轨迹</summary><pre>{JSON.stringify({ base_versions: batch.base_versions, changes: batch.changes, decisions: batch.decisions, audit: batch.audit }, null, 2)}</pre></details>
      {batch.status !== 'PUBLISHED' && <>
        <label className="check"><input type="checkbox" checked={!!confirmed[batch.id]} onChange={e => setConfirmed({ ...confirmed, [batch.id]: e.target.checked })} />我已核对来源、适用范围和上述变更</label>
        <button className="primary" disabled={busy || !confirmed[batch.id]} onClick={async () => { setBusy(true); setError(''); try {
          await api(`${prefix}/batches/${batch.id}/publish`, { method: 'POST', body: { kind: batch.kind } });
          await refresh(); onPublished();
        } catch (e) { setError(message(e)); } finally { setBusy(false); } }}>发布完整新版本</button>
      </>}
    </article>)}
    {!batches.length && <p className="empty">暂无变更批次</p>}
  </section>;
}

export function SchemaPage({ company }: { company: string }) {
  const [text, setText] = useState('');
  const [simulated, setSimulated] = useState(true);
  const [drafts, setDrafts] = useState<any[]>([]);
  const [active, setActive] = useState<any>();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { api('/v1/manage/schema-drafts').then(setDrafts).catch(e => setError(message(e)));
    api('/v1/manage/schemas/active').then(setActive).catch(e => setError(message(e))); }, []);
  return <div className="two-col"><section className="panel"><h2>提出新的信息或关系</h2>
    <p className="muted">模型发现缺口并起草新版本。通过 Git 审阅、生成、测试和部署后，审核人再显式启用。</p>
    <label>新陈述或原文<textarea className="source-text" value={text} onChange={e => setText(e.target.value)} /></label>
    <label className="check"><input type="checkbox" checked={simulated} onChange={e => setSimulated(e.target.checked)} />这是模拟材料</label>
    {error && <p role="alert" className="alert error">{error}</p>}
    <button className="primary" disabled={busy || !text.trim()} onClick={async () => { setBusy(true); setError(''); try {
      const draft = await api('/v1/manage/schema-gaps', { method: 'POST', body: { text, simulated, category_key: 'computer' } });
      setDrafts([...drafts, draft]); setText('');
    } catch (e) { setError(message(e)); } finally { setBusy(false); } }}>{busy ? '起草中…' : '起草待审版本'}</button>
    <hr /><h3>当前启用版本：{active?.version ?? '尚未启用'}</h3>
    <p className="version">{active?.yaml_sha256}</p>
    <p className="muted">页面不能直接启用草案。完成审阅和部署后执行：</p><pre>activate-schema {company} computer &lt;版本&gt;</pre>
  </section><section className="panel"><h2>独立待审草案</h2>
    {drafts.map(draft => <article className="record" key={draft.id}><h3>{draft.gap.proposal.description}</h3><span className="tag pending">{draft.status}</span>
      <p>{draft.gap.base_version} → {draft.artifacts?.version ?? '生成失败'}</p><blockquote>{draft.gap.source_span.quote}</blockquote>
      <p className="version">{draft.artifacts?.branch ?? draft.error_code}</p>
      {draft.artifacts && <details><summary>查看 YAML 差异</summary><pre>{draft.artifacts.diff}</pre></details>}
    </article>)}
    {!drafts.length && <p className="empty">暂无草案。提取中有依据的未映射建议也会进入这里。</p>}
  </section></div>;
}
