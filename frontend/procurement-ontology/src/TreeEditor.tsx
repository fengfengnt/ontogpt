import { useEffect, useState } from 'react';
import { api, message, type Batch, type Tree, type TreeNode } from './api';

export default function TreeEditor({ prefix, onPending, readOnly = false }: {
  prefix: string; onPending: (batch: Batch) => void; readOnly?: boolean;
}) {
  const [tree, setTree] = useState<Tree>();
  const [selected, setSelected] = useState<TreeNode>();
  const [creatingRoot, setCreatingRoot] = useState(false);
  const [name, setName] = useState('');
  const [parent, setParent] = useState('');
  const [categoryKey, setCategoryKey] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { api(prefix + '/tree').then(setTree).catch(e => setError(message(e))); }, [prefix]);
  function select(node: TreeNode) { setSelected(node); setCreatingRoot(false); setName(node.label); setParent(node.parent_id ?? ''); }
  async function save(op: string) {
    if (!tree || (!selected && !creatingRoot) || busy) return;
    const target = creatingRoot ? { id: '', level: 0, parent_id: null } : selected!;
    if (op === 'add_node' && target.level >= 3) { setError('二级品类不能新增第四层'); return; }
    setBusy(true); setError('');
    try {
      const change = op === 'remove_node' ? { op, id: target.id } : { op, node: {
        id: op === 'add_node' ? crypto.randomUUID() : target.id, label: name,
        level: op === 'add_node' ? target.level + 1 : target.level,
        parent_id: op === 'add_node' ? target.id || null : parent || null,
      }, ...(op === 'add_node' && target.level === 2 ? { category_key: categoryKey } : {}) };
      onPending(await api(prefix + '/tree', { method: 'POST', body: { change, observed_version: tree.versions } }));
    } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }
  function branch(parentId: string | null): React.ReactNode {
    return <ul className="tree">{tree?.nodes.filter(n => n.parent_id === parentId).map(node => <li key={node.id}>
      <button aria-pressed={selected?.id === node.id} onClick={() => select(node)}>{node.label}</button>
      {branch(node.id)}
    </li>)}</ul>;
  }
  return <>
    <p className="muted">采购负责类 → 一级品类 → 二级品类。分类变更保存为待发布批次。</p>
    {error && <p role="alert" className="alert error">{error}</p>}
    {tree ? <div className="two-col"><section className="panel"><h2>三级分类树</h2>
      {!readOnly && <button onClick={() => { setCreatingRoot(true); setSelected(undefined); setName(''); }}>新增采购负责类</button>}{branch(null)}
      <p className="version">树版本：{tree.versions.tree}</p></section>
      <section className="panel"><h2>节点属性</h2>{creatingRoot ? <>
        <label>节点名称<input required value={name} onChange={e => setName(e.target.value)} /></label>
        <button className="primary" disabled={busy || !name.trim()} onClick={() => save('add_node')}>保存新节点</button>
      </> : selected ? <>
        <span className="tag">第 {selected.level} 层</span><p className="version">{selected.id}</p>
        <label>节点名称<input value={name} disabled={readOnly} onChange={e => setName(e.target.value)} /></label>
        {selected.level > 1 && <label>父级节点<select value={parent} disabled={readOnly} onChange={e => setParent(e.target.value)}>
          {tree.nodes.filter(n => n.level === selected.level - 1).map(n => <option key={n.id} value={n.id}>{n.label}</option>)}
        </select></label>}
        {selected.level === 2 && <label>新增二级品类键<input value={categoryKey} placeholder="例如 computer" onChange={e => setCategoryKey(e.target.value)} /></label>}
        {!readOnly && <div className="toolbar">
          <button className="primary" disabled={busy || !name.trim()} onClick={() => save('update_node')}>保存修改</button>
          <button disabled={busy || selected.level >= 3 || !name.trim() || (selected.level === 2 && !categoryKey.trim())} onClick={() => save('add_node')}>新增下级</button>
          <button className="danger" disabled={busy} onClick={() => save('remove_node')}>提交删除</button>
        </div>}
        <small>新增下级时，请先在“节点名称”中填写新节点名。删除会检查已发布本体引用。</small>
      </> : <p className="empty">选择左侧节点查看属性</p>}</section></div> : <p role="status">加载分类树…</p>}
  </>;
}
