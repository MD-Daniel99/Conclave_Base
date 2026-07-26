import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

const srcPath = new URL('./src', import.meta.url).pathname

export default defineConfig({
  base: '/app/',
  plugins: [vue()],
  resolve: {
    alias: {
      '@': srcPath,
    },
  },
  server: {
    port: 5173,
    strictPort: true,
  },
})
