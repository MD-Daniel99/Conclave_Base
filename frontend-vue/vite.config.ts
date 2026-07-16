import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

const srcPath = new URL('./src', import.meta.url).pathname

export default defineConfig({
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
