import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from "path"

// Em desenvolvimento, as chamadas a /api são repassadas ao backend. Assim o
// frontend e a API ficam na mesma origem (sem CORS) e o fluxo de etapas das
// consultas (SSE) passa pelo mesmo endereço. No Docker, API_PROXY_TARGET
// aponta para o serviço "backend" (ver docker-compose.yml).
const apiTarget = process.env.API_PROXY_TARGET || "http://localhost:8000"

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      "/api": { target: apiTarget, changeOrigin: true },
    },
  },
})
