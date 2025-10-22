import BackgroundFX from "./components/BackgroundFX";
import Navbar from "./components/Navbar";
import Hero from "./components/Hero";
import Dashboard from "./components/Dashboard";

export default function App() {
  return (
    <>
      <BackgroundFX />
      <Navbar />
      <main className="pt-20">
        <Hero />
        <Dashboard />
      </main>
    </>
  );
}
