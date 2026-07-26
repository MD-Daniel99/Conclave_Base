import vue from '@vitejs/plugin-vue';
import { defineConfig } from 'vite';
var srcPath = new URL('./src', import.meta.url).pathname;
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
        proxy: {
            '/auth': 'http://localhost:8000',  
            '/clients': 'http://localhost:8000',
            '/agents': 'http://localhost:8000',
            '/modules': 'http://localhost:8000',
            '/documents': 'http://localhost:8000',
            '/references': 'http://localhost:8000',
            '/accounting': 'http://localhost:8000',
            '/audit': 'http://localhost:8000',
            '/status': 'http://localhost:8000',
            '/stages': 'http://localhost:8000',
            '/phones': 'http://localhost:8000',
            '/passports': 'http://localhost:8000',
            '/snils': 'http://localhost:8000',
        },
    },
});
