import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const backendTarget = loadEnv(mode, process.cwd(), 'CAMPUSHIELD_').CAMPUSHIELD_API_TARGET || 'http://127.0.0.1:8000'
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: backendTarget,
          changeOrigin: true,
          ws: true
        },
        '/healthz': {
          target: backendTarget,
          changeOrigin: true
        },
        '/snapshots': {
          target: backendTarget,
          changeOrigin: true
        },
        '/enrollments': {
          target: backendTarget,
          changeOrigin: true
        }
      }
    }
  }
})
