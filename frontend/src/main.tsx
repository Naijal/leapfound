<<<<<<< HEAD
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App";

const el = document.getElementById("root");
if (el) {
  createRoot(el).render(<App />);
} else {
  console.error("Root element #root not found");
}
=======
import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import App from './App'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
>>>>>>> b24514b (Initial Leapfound (backend FastAPI + frontend Vite))
