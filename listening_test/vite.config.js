import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// `npm run dev` forwards /api to the Python server (python serve.py, port 8765).
// For the real test, build once (`npm run build`) and let serve.py serve dist/ itself.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true, proxy: { '/api': 'http://127.0.0.1:8765' } },
  build: { outDir: 'dist', emptyOutDir: true, assetsInlineLimit: 0 },
});
