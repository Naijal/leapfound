import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App";

const el = document.getElementById("root");
if (el) {
  createRoot(el).render(<App />);
} else {
  console.error("Root element #root not found");
}
