import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

/* Optional dev proxy: run with VM_PROXY_TARGET=http://<vm-host>:8428 npm run dev,
   then set the app data source to "/vm" (same-origin, no CORS). */
const VM = process.env.VM_PROXY_TARGET || 'http://localhost:8428'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/vm': { target: VM, changeOrigin: true, rewrite: p => p.replace(/^\/vm/, '') },
    },
  },
  preview: {
    port: 4173,
    proxy: {
      '/vm': { target: VM, changeOrigin: true, rewrite: p => p.replace(/^\/vm/, '') },
    },
  },
})
