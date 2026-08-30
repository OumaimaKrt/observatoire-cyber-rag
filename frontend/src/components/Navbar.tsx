import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import { 
  LayoutDashboard, 
  AlertTriangle, 
  MessageSquare, 
  FileText,
  Shield,
  Menu,
  X
} from 'lucide-react';
import { cn } from '../lib/utils';

const navItems = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/incidents', label: 'Incidents', icon: AlertTriangle },
  { path: '/chat', label: 'Assistant', icon: MessageSquare },
  { path: '/reports', label: 'Rapports', icon: FileText },
];

export default function Navbar() {
  const location = useLocation();
  const [isOpen, setIsOpen] = useState(false);

  return (
    <nav className="sticky top-0 z-50 bg-surface/95 backdrop-blur-lg border-b border-border">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <Link to="/" className="flex items-center gap-3">
            <div className="relative">
              <Shield className="w-8 h-8 text-gold" />
              <div className="absolute -top-1 -right-1 w-2 h-2 bg-gold rounded-full animate-pulse" />
            </div>
            <span className="text-xl font-display font-bold text-text tracking-tight">
              Observatoire<span className="text-gold">Cyber</span>
            </span>
          </Link>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center gap-1">
            {navItems.map(({ path, label, icon: Icon }) => (
              <Link key={path} to={path}>
                <span
                  className={cn(
                    "inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200",
                    location.pathname === path
                      ? "bg-gold/10 text-gold border border-gold/20"
                      : "text-textMuted hover:text-text hover:bg-surfaceLight"
                  )}
                >
                  <Icon className="w-4 h-4" />
                  {label}
                </span>
              </Link>
            ))}
          </div>

          {/* Mobile Menu Button */}
          <button
            className="md:hidden p-2 rounded-lg hover:bg-surfaceLight transition-colors text-text"
            onClick={() => setIsOpen(!isOpen)}
          >
            {isOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {/* Mobile Navigation */}
      {isOpen && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          className="md:hidden border-t border-border bg-surface"
        >
          <div className="px-4 py-2 space-y-1">
            {navItems.map(({ path, label, icon: Icon }) => (
              <Link key={path} to={path} onClick={() => setIsOpen(false)}>
                <span className="flex items-center gap-3 px-4 py-2 rounded-lg text-sm font-medium text-textMuted hover:text-text hover:bg-surfaceLight transition-colors">
                  <Icon className="w-4 h-4" />
                  {label}
                </span>
              </Link>
            ))}
          </div>
        </motion.div>
      )}
    </nav>
  );
}