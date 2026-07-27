import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.ico', 'favicon-32.png', 'app-logo.png', 'elv-logo.png'],
      manifest: {
        name: 'ELV ALC Dashboard',
        short_name: 'ALC Dashboard',
        description: 'Web UI for ELV / Voltcraft ALC chargers',
        theme_color: '#1f628f',
        background_color: '#1f628f',
        display: 'standalone',
        start_url: '/',
        scope: '/',
        lang: 'de',
        icons: [
          {
            src: 'pwa-192.png',
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: 'pwa-512.png',
            sizes: '512x512',
            type: 'image/png',
          },
          {
            src: 'pwa-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
      workbox: {
        navigateFallback: 'index.html',
        // Export-Links (/api/archive/.../pdf|csv) are top-level navigations — must not get the SPA shell
        navigateFallbackDenylist: [/^\/api\//, /^\/ws/],
        runtimeCaching: [
          {
            urlPattern: ({ url }) => url.pathname.startsWith('/api/') || url.pathname.startsWith('/ws'),
            handler: 'NetworkOnly',
          },
        ],
      },
    }),
  ],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8080',
      '/ws': { target: 'ws://127.0.0.1:8080', ws: true },
    },
  },
})
