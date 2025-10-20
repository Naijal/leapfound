import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

<<<<<<< HEAD
// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
=======
export default defineConfig({
  plugins: [react()],
  base: '/static/',   // serve under /static/
>>>>>>> b24514b (Initial Leapfound (backend FastAPI + frontend Vite))
})
