import { build } from 'esbuild';
import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('.', import.meta.url));
const result = await build({ absWorkingDir: root, entryPoints: ['app.jsx'], bundle: true, write: false, minify: true, format: 'iife', target: 'es2022', define: { 'process.env.NODE_ENV': '"production"' } });
const css = await readFile(new URL('style.css', import.meta.url), 'utf8');
const html = `<!doctype html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>OntoGPT · 管理台设计预览</title><style>${css}</style></head><body><div id="root"></div><script>${result.outputFiles[0].text.replaceAll('</script', '<\\/script')}</script></body></html>`;
await writeFile(new URL('workspace-prototype.html', import.meta.url), html);
console.log(`已构建独立草图：${root}workspace-prototype.html (${Math.round(Buffer.byteLength(html) / 1024)} KB)`);
