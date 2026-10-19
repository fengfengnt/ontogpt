import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: { port: 5174, proxy: { '/v1': 'http://127.0.0.1:8002' } },
  test: { environment: 'jsdom', globals: true, setupFiles: ['./src/testSetup.ts'] },
});
