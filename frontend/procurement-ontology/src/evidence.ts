import type { Source, Span } from './api';

export function evidence(source: Source, quote: string): Span {
  const index = source.text.indexOf(quote);
  if (!quote || index < 0 || source.text.indexOf(quote, index + 1) >= 0) throw new Error('摘录需要在所选原文中唯一定位，请补充前后文');
  const start = Array.from(source.text.slice(0, index)).length;
  return { revision_id: source.id, start, end: start + Array.from(quote).length, quote };
}
