import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/start':  'http://localhost:8000',
      '/stop':   'http://localhost:8000',
      '/status': 'http://localhost:8000',
      '/stream': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
