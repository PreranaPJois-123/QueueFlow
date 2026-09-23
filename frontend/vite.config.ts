import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ command, mode }) => {
  if (command === 'build') {
    const apiUrl = process.env.VITE_API_URL || loadEnv(mode, process.cwd(), 'VITE_').VITE_API_URL
    if (!apiUrl) throw new Error('Set VITE_API_URL to the public backend origin before building')
    const url = new URL(apiUrl)
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password ||
        url.search || url.hash || (url.pathname !== '' && url.pathname !== '/')) {
      throw new Error('VITE_API_URL must be an HTTP(S) origin without credentials, query, or path')
    }
    if (process.env.RENDER && (url.protocol !== 'https:' ||
        ['localhost', '127.0.0.1', '::1', '[::1]'].includes(url.hostname) || !url.hostname.includes('.'))) {
      throw new Error('Render builds require a public HTTPS backend URL')
    }
  }
  return { plugins: [react(), tailwindcss()], server: { port: 5173 } }
})
