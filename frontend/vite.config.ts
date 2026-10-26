import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

const api = process.env.LEDGERX_API_URL || 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  build: { outDir: '../app/web', emptyOutDir: true, target: 'es2022' },
  server: {
    strictPort: true,
    proxy: Object.fromEntries(
      [
        '/auth',
        '/accounts',
        '/transfers',
        '/dev',
        '/operations',
        '/health',
        '/docs',
        '/openapi.json',
        '/metrics',
      ].map((path) => [path, { target: api }]),
    ),
  },
  test: { include: ['tests/**/*.test.ts'], environment: 'node' },
});
