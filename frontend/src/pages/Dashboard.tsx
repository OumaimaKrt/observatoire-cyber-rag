// frontend/src/pages/Dashboard.tsx
import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { 
  Activity, 
  Shield, 
  AlertTriangle, 
  Building2,
  Zap,
  TrendingUp,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { getDashboardStats } from '../services/api';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  CartesianGrid
} from 'recharts';

const COLORS = ['#C9932E', '#E67A4A', '#4A7C8E', '#C4453D', '#2A5C6E', '#5A8A6A', '#8A6A5A'];

// 🔥 Filtrer les données pour exclure les "INCONNU"
const filterUnknown = (data: any[], key: string) => {
  if (!data) return [];
  return data.filter(item => {
    const value = item[key] || '';
    return value !== 'INCONNU' && value !== '' && value !== null;
  });
};

// Stats Cards
const statsCards = [
  { 
    title: 'Total Incidents', 
    key: 'total_incidents', 
    icon: Activity, 
    color: 'text-gold', 
    bg: 'bg-gold/10',
    subtitle: 'Incidents enregistrés'
  },
  { 
    title: 'Types de Menaces', 
    key: 'unique_threat_types', 
    icon: Shield, 
    color: 'text-[#4A7C8E]', 
    bg: 'bg-[#4A7C8E]/10',
    subtitle: 'Types identifiés'
  },
  { 
    title: 'Alertes Critiques', 
    key: 'critical_alerts', 
    icon: AlertTriangle, 
    color: 'text-alert', 
    bg: 'bg-alert/10',
    subtitle: 'Niveau critique'
  },
  { 
    title: 'Secteurs Touchés', 
    key: 'sectors_affected', 
    icon: Building2, 
    color: 'text-[#E67A4A]', 
    bg: 'bg-[#E67A4A]/10',
    subtitle: 'Secteurs impactés'
  },
];

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-[#0F1B2D] border border-gold rounded-lg px-4 py-2 shadow-lg shadow-gold/10">
        <p className="text-gold font-semibold text-sm">{label}</p>
        <p className="text-text font-bold text-lg">{`${payload[0].value}`}</p>
      </div>
    );
  }
  return null;
};

export default function Dashboard() {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        setLoading(true);
        const response = await getDashboardStats();
        setStats(response.data);
        setError(null);
      } catch (err) {
        console.error('Erreur API:', err);
        setError('Impossible de charger les données. Vérifiez que le backend Django est en cours d\'exécution.');
        setStats(null);
      } finally {
        setLoading(false);
      }
    };
    fetchStats();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="relative">
          <div className="animate-spin rounded-full h-12 w-12 border-2 border-gold/20 border-t-gold"></div>
          <div className="absolute inset-0 flex items-center justify-center">
            <Shield className="w-5 h-5 text-gold/50" />
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="bg-alert/10 border border-alert/30 text-alert p-6 rounded-lg max-w-md text-center">
          <AlertTriangle className="w-12 h-12 mx-auto mb-3" />
          <p className="text-lg font-semibold">Erreur de chargement</p>
          <p className="text-sm mt-2">{error}</p>
          <button 
            onClick={() => window.location.reload()}
            className="mt-4 px-4 py-2 bg-gold text-[#0F1B2D] rounded-lg hover:bg-goldLight transition-colors"
          >
            Réessayer
          </button>
        </div>
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-textMuted text-center">
          <p>Aucune donnée disponible</p>
        </div>
      </div>
    );
  }

  // 🔥 Filtrer les données pour les graphiques (exclut toujours les INCONNU)
  const topTypesFiltered = filterUnknown(stats.top_types || [], 'type');
  const topSectorsFiltered = filterUnknown(stats.top_sectors || [], 'secteur');

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8"
    >
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-8">
        <div>
          <h1 className="text-3xl font-display font-bold text-text">Tableau de bord</h1>
          <p className="text-textMuted text-sm mt-1">Vue d'ensemble des cybermenaces au Maroc</p>
        </div>
        <span className="text-sm text-textMuted bg-surfaceLight px-3 py-1.5 rounded-full border border-border flex items-center gap-2">
          <Zap className="w-3 h-3 text-gold" />
          Données réelles
        </span>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {statsCards.map((card, index) => {
          const value = stats?.[card.key] || 0;
          return (
            <motion.div
              key={card.title}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
            >
              <Card className="border-border bg-surface/30 hover:bg-surface/50 transition-all duration-300">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-textMuted">{card.title}</p>
                      <p className="text-2xl font-bold text-text mt-1 font-display">
                        {value.toLocaleString()}
                      </p>
                      <p className="text-xs text-textMuted mt-0.5">{card.subtitle}</p>
                    </div>
                    <div className={`p-3 rounded-lg ${card.bg}`}>
                      <card.icon className={`w-5 h-5 ${card.color}`} />
                    </div>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          );
        })}
      </div>

      <div className="zellige-divider" />

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-8">
        {/* Top 5 Menaces */}
        <Card className="border-border bg-surface/30 hover:bg-surface/50 transition-all duration-300">
          <CardHeader>
            <CardTitle className="text-text flex items-center justify-between">
              <span className="flex items-center gap-2">
                <span className="text-gold">●</span>
                Top 5 Menaces
              </span>
              <span className="text-xs text-textMuted font-normal">
                {topTypesFiltered.length} types
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {topTypesFiltered.length === 0 ? (
              <div className="h-[300px] flex items-center justify-center text-textMuted">
                <p>Aucune donnée disponible</p>
              </div>
            ) : (
              <div className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={topTypesFiltered}>
                    <CartesianGrid stroke="#2A3A5A" strokeDasharray="3 3" />
                    <XAxis dataKey="type" stroke="#B0B0C0" fontSize={12} tick={{ fill: '#B0B0C0' }} />
                    <YAxis stroke="#B0B0C0" fontSize={12} tick={{ fill: '#B0B0C0' }} />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar 
                      dataKey="count" 
                      fill="#C9932E" 
                      radius={[4, 4, 0, 0]} 
                      fillOpacity={0.85}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Top 5 Secteurs */}
        <Card className="border-border bg-surface/30 hover:bg-surface/50 transition-all duration-300">
          <CardHeader>
            <CardTitle className="text-text flex items-center justify-between">
              <span className="flex items-center gap-2">
                <span className="text-[#4A7C8E]">●</span>
                Top 5 Secteurs
              </span>
              <span className="text-xs text-textMuted font-normal">
                {topSectorsFiltered.length} secteurs
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {topSectorsFiltered.length === 0 ? (
              <div className="h-[300px] flex items-center justify-center text-textMuted">
                <p>Aucune donnée disponible</p>
              </div>
            ) : (
              <div className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={topSectorsFiltered}
                      dataKey="count"
                      nameKey="secteur"
                      cx="50%"
                      cy="50%"
                      innerRadius={50}
                      outerRadius={100}
                      paddingAngle={2}
                      label={({ secteur, percent }) => 
                        `${secteur} ${(percent * 100).toFixed(1)}%`
                      }
                      labelLine={{ stroke: '#8A8A8A', strokeWidth: 1 }}
                    >
                      {topSectorsFiltered.map((_: any, index: number) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip content={<CustomTooltip />} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Timeline */}
      <div className="mt-8">
        <Card className="border-border bg-surface/30 hover:bg-surface/50 transition-all duration-300">
          <CardHeader>
            <CardTitle className="text-text flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-gold" />
              Évolution des incidents
            </CardTitle>
          </CardHeader>
          <CardContent>
            {!stats?.timeline || stats.timeline.length === 0 ? (
              <div className="h-[250px] flex items-center justify-center text-textMuted">
                <p>Aucune donnée disponible</p>
              </div>
            ) : (
              <div className="h-[250px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={stats.timeline}>
                    <CartesianGrid stroke="#2A3A5A" strokeDasharray="3 3" />
                    <XAxis dataKey="date" stroke="#B0B0C0" fontSize={12} tick={{ fill: '#B0B0C0' }} />
                    <YAxis stroke="#B0B0C0" fontSize={12} tick={{ fill: '#B0B0C0' }} />
                    <Tooltip content={<CustomTooltip />} />
                    <Line 
                      type="monotone" 
                      dataKey="incidents" 
                      stroke="#C9932E" 
                      strokeWidth={2}
                      dot={{ fill: '#C9932E', strokeWidth: 2 }}
                      activeDot={{ r: 8, fill: '#C9932E' }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </motion.div>
  );
}