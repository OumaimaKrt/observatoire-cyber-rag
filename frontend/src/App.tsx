import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import Navbar from './components/Navbar';
import Dashboard from './pages/Dashboard';
import Incidents from './pages/Incidents';
import Chatbot from './pages/Chatbot';
import Reports from './pages/Reports';

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-background zellige-pattern">
        <Navbar />
        <AnimatePresence mode="wait">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/incidents" element={<Incidents />} />
            <Route path="/chat" element={<Chatbot />} />
            <Route path="/reports" element={<Reports />} />
          </Routes>
        </AnimatePresence>
        
        {/* Filigrane zellige en bas à droite */}
        <div className="fixed bottom-4 right-4 opacity-10 pointer-events-none">
          <svg width="80" height="80" viewBox="0 0 80 80">
            <pattern id="zellige-watermark" x="0" y="0" width="20" height="20" patternUnits="userSpaceOnUse">
              <path d="M10 0 L20 10 L10 20 L0 10 Z" fill="none" stroke="#C9932E" strokeWidth="0.5" />
              <path d="M10 5 L15 10 L10 15 L5 10 Z" fill="none" stroke="#C9932E" strokeWidth="0.5" />
            </pattern>
            <rect width="80" height="80" fill="url(#zellige-watermark)" />
          </svg>
        </div>
      </div>
    </BrowserRouter>
  );
}

export default App;