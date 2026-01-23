import path from 'path'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { viteStaticCopy } from 'vite-plugin-static-copy'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    // Copy staticwebapp.config.json to dist for Azure Static Web Apps
    viteStaticCopy({
      targets: [
        {
          src: 'staticwebapp.config.json',
          dest: '.'
        }
      ]
    })
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './frontend'),
    },
  },
})
