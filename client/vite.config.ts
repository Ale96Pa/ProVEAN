import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
    server: {
        proxy: {
            "/socket.io": {
                target: "http://localhost:46715/",
                changeOrigin: true,
                ws: true,
            }
        }
    },
    resolve: {
        alias: {
            "@components": path.resolve(__dirname, 'src/components'),
            "@lib": path.resolve(__dirname, 'src/lib'),
        }
    },
    plugins: [svelte()],
})
