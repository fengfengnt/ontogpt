import { useState } from 'react';
import { evidence } from './evidence';
import type { Item, Source, Tree } from './api';

export const kindLabels: Record<string, string> = {
  CollectionField: '信息采集项', ConditionTemplate: '条件模板', TermDefinition: '术语定义', ProcessNote: '流程提示',
  CompanyStatement: '企业陈述', QualificationStatement: '资质说明', BrandAuthorization: '品牌授权',
  ProductOffering: '产品方案', DeliveryServiceCapability: '交付服务能力', ProjectEvidence: '项目记录',
  InternalCost: '内部成本', PricingStrategy: '报价策略',
};
const fieldLabels: Record<string, string> = {
  field_name: '采集字段', question: '建议询问', data_type: '数据类型', unit: '单位', example_value: '项目示例',
  condition_category: '条件类别', condition_text: '条件内容', requested_supplier_data: '供应商需提供的信息', case_threshold: '本项目门槛',
  term: '术语', definition: '定义', distinguish_from: '区分说明', guidance: '流程说明',
  cost_type: '成本类型', amount_text: '金额原文', currency: '币种', tax_basis: '税务口径', amount_basis: '金额口径', estimate_text: '估算说明',
  strategy_type: '策略类型', concession_text: '让步内容', reason: '原因', brand: '品牌', model_name: '型号', configuration_text: '配置说明',
  included_service_text: '包含服务', region: '覆盖区域', quantity_text: '数量原文', lead_time_text: '交期', service_provider: '服务提供方',
  warranty_years_text: '保修年限', service_mode: '服务方式', response_time_text: '响应时效', validity_text: '有效期原文',
};
const envelope = new Set(['local_ref', 'label', 'statement', 'evidence_quote', 'evidence_start', 'evidence_end', 'project_ref', 'stage', 'device_type']);

export default function KnowledgeEditor({ initial, sources, tree, schema, onSave, onCancel }: {
  initial?: Item; sources: Source[]; tree: Tree; schema?: any; onSave: (item: Item) => Promise<void>; onCancel?: () => void;
}) {
  const [item, setItem] = useState<Item>(initial ?? { id: crypto.randomUUID(), kind: schema?.item_types[0] ?? 'TermDefinition', label: '', description: '',
    category_id: Object.values(tree.category_keys)[0] ?? '', properties: {}, scope: {}, source_spans: [], simulated: true, schema_version: schema?.version ?? null, access_policy_ref: null });
  const [sourceId, setSourceId] = useState(initial?.source_spans[0]?.revision_id ?? sources[0]?.id ?? '');
  const [quote, setQuote] = useState(initial?.source_spans[0]?.quote ?? '');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const definitions = schema?.json_schema?.$defs ?? {};
  const properties = definitions[item.kind]?.properties ?? {};
  const businessFields = Object.entries(properties).filter(([key]) => !envelope.has(key));
  async function save(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const source = sources.find(s => s.id === sourceId);
      if (!source) throw new Error('请选择已保存的来源');
      await onSave({ ...item, source_spans: [evidence(source, quote)], simulated: source.simulated });
    } catch (e) { setError(e instanceof Error ? e.message : '保存失败'); } finally { setBusy(false); }
  }
  return <form onSubmit={save}>
    <div className="form-grid">
      <label>条目名称<input required value={item.label} onChange={e => setItem({ ...item, label: e.target.value })} /></label>
      <label>业务类型{schema ? <select value={item.kind} onChange={e => setItem({ ...item, kind: e.target.value, properties: {} })}>
        {schema.item_types.map((kind: string) => <option key={kind} value={kind}>{kindLabels[kind] ?? kind}</option>)}
      </select> : <input required value={item.kind} onChange={e => setItem({ ...item, kind: e.target.value })} />}</label>
    </div>
    <label>业务说明<textarea value={item.description} onChange={e => setItem({ ...item, description: e.target.value })} /></label>
    <label>归属二级品类<select value={item.category_id} onChange={e => setItem({ ...item, category_id: e.target.value })}>
      {tree.nodes.filter(n => n.level === 3).map(n => <option key={n.id} value={n.id}>{n.label}</option>)}
    </select></label>
    <div className="form-grid">{[['project_ref', '项目编号'], ['device_type', '设备类型'], ['stage', '阶段'], ['valid_from', '生效日期'], ['valid_to', '失效日期']].map(([key, label]) =>
      <label key={key}>{label}<input type={key.startsWith('valid_') ? 'date' : 'text'} value={item.scope[key] ?? ''}
        onChange={e => setItem({ ...item, scope: { ...item.scope, [key]: e.target.value || null } })} /></label>)}</div>
    {businessFields.length > 0 && <><h3>业务属性</h3><div className="form-grid">{businessFields.map(([key, definition]) => {
      const field = definition as any;
      const enumRef = field.$ref ?? field.anyOf?.find((value: any) => value.$ref)?.$ref;
      const options = enumRef ? definitions[enumRef.split('/').pop()]?.enum : undefined;
      return <label key={key}>{fieldLabels[key] ?? key}{options ? <select value={item.properties[key] ?? ''}
        onChange={e => setItem({ ...item, properties: { ...item.properties, [key]: e.target.value || null } })}>
        <option value="">未说明</option>{options.map((value: string) => <option key={value}>{value}</option>)}</select>
        : <input value={item.properties[key] ?? ''} onChange={e => setItem({ ...item, properties: { ...item.properties, [key]: e.target.value || null } })} />}</label>;
    })}</div></>}
    <h3>原文依据</h3>
    <label>来源修订<select value={sourceId} onChange={e => setSourceId(e.target.value)}>
      <option value="">请选择</option>{sources.map(source => <option key={source.id} value={source.id}>{source.simulated ? '模拟 · ' : ''}{source.text.slice(0, 35)} · {source.id.slice(-8)}</option>)}
    </select></label>
    <details><summary>查看所选原文</summary><blockquote>{sources.find(s => s.id === sourceId)?.text}</blockquote></details>
    <label>逐字摘录<textarea required value={quote} onChange={e => setQuote(e.target.value)} placeholder="摘录需在所选原文中唯一出现" /></label>
    {error && <p role="alert" className="alert error">{error}</p>}
    <div className="toolbar"><button className="primary" disabled={busy}>{busy ? '保存中…' : '保存到待审批次'}</button>
      {onCancel && <button type="button" onClick={onCancel}>取消</button>}</div>
  </form>;
}
