import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/query': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false
      },
      '/health': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false
      },
      '/upcoming': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false
      },
      '/today-matches': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false
      },
      '/team-stats': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false
      },
      '/bracket': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false
      },
      '/leaderboards': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false
      },
      '/player-finder': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false
      },
      '/tournament-overview': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false
      }
    }
  }
})
