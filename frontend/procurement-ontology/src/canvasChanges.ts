import type { Item, Relation, Versions } from './api';

const allowed = new Set(['add_item', 'update_item', 'remove_item', 'add_relation', 'update_relation', 'remove_relation']);

export function toChange(selected: Item | Relation | any, operation: string, observed_version: Versions, allowedRelations: string[]) {
  if (!allowed.has(operation) || selected.level !== undefined) throw new Error('画布只允许修改业务条目和关系');
  const relation = operation.endsWith('_relation');
  if (!operation.startsWith('remove_')) {
    if (!selected.source_spans?.length) throw new Error('变更需要原文依据');
    if (relation && !allowedRelations.includes(selected.predicate)) throw new Error('关系不属于当前启用的 schema');
  }
  const change = operation.startsWith('remove_') ? { op: operation, id: selected.id }
    : { op: operation, [relation ? 'relation' : 'item']: selected };
  return { change, observed_version };
}
