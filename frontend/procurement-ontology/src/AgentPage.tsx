import { useState } from 'react';
import { api, message } from './api';

export default function AgentPage() {
  const [question, setQuestion] = useState('');
  const [result, setResult] = useState<any>();
  const [detail, setDetail] = useState<any>();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  return <div className="two-col"><section className="panel"><h2>向本企业知识提问</h2>
    <p className="muted">知识范围固定为甲方的电脑二级品类，只使用已发布条目。答案保留实际版本和原文依据。</p>
    <form onSubmit={async event => { event.preventDefault(); setBusy(true); setError(''); setDetail(undefined); try {
      setResult(await api('/v1/agent/questions', { method: 'POST', body: { question } }));
    } catch (e) { setError(message(e)); } finally { setBusy(false); } }}>
      <label>问题<textarea required maxLength={2000} value={question} onChange={e => setQuestion(e.target.value)} placeholder="例如：这个项目应如何询问保修方式？" /></label>
      <button className="primary" disabled={busy || !question.trim()}>{busy ? '查询并核对依据…' : '基于已发布本体回答'}</button>
    </form>
    {error && <p role="alert" className="alert error">{error}</p>}
    {result && <article className="record"><h3>回答</h3><p style={{ whiteSpace: 'pre-wrap' }}>{result.answer}</p>
      <p className="version">树：{result.versions.tree}<br />本体：{result.versions.ontology}</p>
    </article>}
  </section><section className="panel"><h2>本次工具引用</h2>
    {result?.citations.map((citation: any) => <article className="record" key={citation.item_id}><h3>{citation.label}</h3>
      {citation.simulated && <span className="tag">模拟资料</span>}<p>项目：{citation.scope.project_ref ?? '未说明'} · 阶段：{citation.scope.stage ?? '未说明'}</p>
      {citation.source_spans.map((span: any, index: number) => <blockquote key={index}>{span.quote}<p className="version">{span.revision_id} [{span.start}, {span.end})</p></blockquote>)}
      <p className="version">{citation.item_id}</p><button onClick={async () => { setError(''); try {
        const params = new URLSearchParams({ tree_version: result.versions.tree, ontology_version: result.versions.ontology });
        setDetail(await api('/v1/ontology/items/' + encodeURIComponent(citation.item_id) + '?' + params));
      } catch (e) { setError(message(e)); } }}>查看条目详情</button>
    </article>)}
    {(!result || !result.citations.length) && <p className="empty">有依据的回答会在这里列出实际条目与来源。</p>}
    {detail && <article className="record"><h3>{detail.item.label}</h3><p>{detail.item.description}</p><pre>{JSON.stringify(detail.item.properties, null, 2)}</pre></article>}
  </section></div>;
}
