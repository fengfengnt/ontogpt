export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message); }
}

export async function api(path: string, options?: { method?: string; body?: unknown }): Promise<any> {
  const response = await fetch(path, {
    credentials: 'same-origin', method: options?.method ?? 'GET',
    headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'procurement-ontology' },
    body: options?.body === undefined ? undefined : JSON.stringify(options.body),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(response.status, result.code ?? 'REQUEST_FAILED', result.message ?? '请求失败，请检查服务状态或重新登录');
  return result;
}

export const message = (error: unknown) => error instanceof Error ? error.message : '操作失败';
export type Identity = { account_id: string; scope_id: string; role: string };
export type Versions = { tree: string; ontology: string };
export type Span = { revision_id: string; start: number; end: number; quote: string };
export type Source = { id: string; text: string; simulated: boolean; sha256: string };
export type Item = { id: string; kind: string; label: string; description: string; category_id: string;
  scope: Record<string, string | null>; properties: Record<string, any>; source_spans: Span[];
  simulated: boolean; schema_version: string | null; access_policy_ref: null };
export type Relation = { id: string; subject_id: string; predicate: string; object_id: string; source_spans: Span[]; scope: Record<string, string | null> };
export type TreeNode = { id: string; label: string; level: number; parent_id: string | null };
export type Tree = { nodes: TreeNode[]; category_keys: Record<string, string>; versions: Versions };
export type Batch = { id: string; kind: 'tree' | 'ontology'; status: string; changes: any[]; decisions: Record<string, any>; base_versions: Versions; audit: any[] };

