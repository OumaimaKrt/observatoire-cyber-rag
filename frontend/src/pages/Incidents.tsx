// frontend/src/pages/Incidents.tsx
import { useState, useEffect, useMemo } from 'react';
import { motion } from 'framer-motion';
import { 
  Search, Filter, Download, Eye, 
  ChevronLeft, ChevronRight, X, AlertTriangle 
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { getIncidents, getSectors, getTypes } from '../services/api';

// Types TypeScript
interface Incident {
  id: number;
  titre: string;
  type_menace: string;
  secteur_cible: string;
  source: string;
  created_at: string;
  description?: string;
  impact?: string;
  solution?: string;
  severite?: string;
}

interface Filters {
  type: string;
  secteur: string;
  search: string;
  source: string;
  dateFrom: string;
  dateTo: string;
}

// 🔥 Couleurs des badges
const getBadgeColor = (type: string) => {
  if (!type || type === 'INCONNU' || type === '') {
    return 'bg-gray-100 text-gray-400 border border-gray-200';
  }
  
  const colors: Record<string, string> = {
    'PIRATAGE': 'bg-red-100 text-red-800',
    'PHISHING': 'bg-orange-100 text-orange-800',
    'RANSOMWARE': 'bg-purple-100 text-purple-800',
    'DDOS': 'bg-blue-100 text-blue-800',
    'CHEVAL_TROIE': 'bg-pink-100 text-pink-800',
    'VULNERABILITE': 'bg-yellow-100 text-yellow-800',
    'MALWARE': 'bg-red-100 text-red-800',
    'INCIDENT': 'bg-gray-100 text-gray-800',
    'SPAM': 'bg-indigo-100 text-indigo-800',
    'FRAUDE': 'bg-rose-100 text-rose-800',
    'RENVOI': 'bg-amber-100 text-amber-800',
  };
  return colors[type] || 'bg-gray-100 text-gray-800';
};

// 🔥 Fonction pour extraire les données
const extractData = (response: any, fallback: any[] = []) => {
  if (!response) return fallback;
  if (response.data && Array.isArray(response.data)) {
    return response.data;
  }
  if (Array.isArray(response)) {
    return response;
  }
  return fallback;
};

export default function Incidents() {
  // États
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [filteredIncidents, setFilteredIncidents] = useState<Incident[]>([]);
  const [sectors, setSectors] = useState<string[]>([]);
  const [types, setTypes] = useState<string[]>([]);
  const [sources, setSources] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage] = useState(10);
  
  const [filters, setFilters] = useState<Filters>({
    type: '',
    secteur: '',
    search: '',
    source: '',
    dateFrom: '',
    dateTo: ''
  });

  // ─────────────────────────────────────────────────────────────
  // 1. CHARGEMENT DES DONNÉES
  // ─────────────────────────────────────────────────────────────
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);
        
        const [incidentsRes, sectorsRes, typesRes] = await Promise.all([
          getIncidents(),
          getSectors(),
          getTypes()
        ]);
        
        const incidentsData = extractData(incidentsRes, []);
        const sectorsData = extractData(sectorsRes, []);
        const typesData = extractData(typesRes, []);
        
        // 🔥 Filtrer les types et secteurs "INCONNU" pour les selecteurs
        const filteredTypes = typesData.filter((t: string) => t !== 'INCONNU' && t !== '');
        const filteredSectors = sectorsData.filter((s: string) => s !== 'INCONNU' && s !== '');
        
        // 🔥 Extraction des sources uniques
        const uniqueSources = incidentsData
          .map((i: Incident) => i.source)
          .filter((s: string | undefined): s is string => 
            typeof s === 'string' && s !== '' && s !== 'INCONNU'
          )
          .filter((s: string, index: number, self: string[]) => 
            self.indexOf(s) === index
          );
        
        setIncidents(incidentsData);
        setFilteredIncidents(incidentsData);
        setSectors(filteredSectors);
        setTypes(filteredTypes);
        setSources(uniqueSources);
        
      } catch (error: any) {
        console.error('Erreur de chargement:', error);
        setError(error.message || 'Erreur lors du chargement des incidents');
        setIncidents([]);
        setFilteredIncidents([]);
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
  }, []);

  // ─────────────────────────────────────────────────────────────
  // 2. FILTRAGE DES DONNÉES - 🔥 EXCLUT TOUJOURS LES INCONNU
  // ─────────────────────────────────────────────────────────────
  useEffect(() => {
    const applyFilters = () => {
      let result = incidents;
      
      // 🔥 TOUJOURS FILTRER LES "INCONNU"
      result = result.filter(incident => 
        incident.type_menace && 
        incident.type_menace !== 'INCONNU' && 
        incident.type_menace !== '' &&
        incident.type_menace !== null
      );
      
      if (filters.search.trim()) {
        const searchTerm = filters.search.toLowerCase().trim();
        result = result.filter(incident => 
          incident.titre?.toLowerCase().includes(searchTerm) ||
          incident.description?.toLowerCase().includes(searchTerm) ||
          incident.type_menace?.toLowerCase().includes(searchTerm) ||
          incident.secteur_cible?.toLowerCase().includes(searchTerm)
        );
      }
      
      if (filters.type) {
        result = result.filter(incident => 
          incident.type_menace === filters.type
        );
      }
      
      if (filters.secteur) {
        result = result.filter(incident => 
          incident.secteur_cible === filters.secteur
        );
      }
      
      if (filters.source) {
        result = result.filter(incident => 
          incident.source === filters.source
        );
      }
      
      if (filters.dateFrom) {
        result = result.filter(incident => 
          new Date(incident.created_at) >= new Date(filters.dateFrom)
        );
      }
      
      if (filters.dateTo) {
        result = result.filter(incident => 
          new Date(incident.created_at) <= new Date(filters.dateTo)
        );
      }
      
      setFilteredIncidents(result);
      setCurrentPage(1);
    };
    
    applyFilters();
  }, [filters, incidents]);

  // ─────────────────────────────────────────────────────────────
  // 3. GESTION DES ÉVÉNEMENTS
  // ─────────────────────────────────────────────────────────────
  const handleFilterChange = (e: React.ChangeEvent<HTMLSelectElement | HTMLInputElement>) => {
    const { name, value } = e.target;
    setFilters(prev => ({ ...prev, [name]: value }));
  };

  const resetFilters = () => {
    setFilters({
      type: '',
      secteur: '',
      search: '',
      source: '',
      dateFrom: '',
      dateTo: ''
    });
  };

  // ─────────────────────────────────────────────────────────────
  // 4. PAGINATION
  // ─────────────────────────────────────────────────────────────
  const totalPages = Math.ceil(filteredIncidents.length / itemsPerPage);
  const currentIncidents = useMemo(() => {
    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    return filteredIncidents.slice(startIndex, endIndex);
  }, [filteredIncidents, currentPage, itemsPerPage]);

  const goToPage = (page: number) => {
    setCurrentPage(Math.max(1, Math.min(page, totalPages)));
  };

  // ─────────────────────────────────────────────────────────────
  // 5. EXPORT DES DONNÉES
  // ─────────────────────────────────────────────────────────────
  const exportData = () => {
    try {
      const headers = ['ID', 'Titre', 'Type', 'Secteur', 'Source', 'Date', 'Description', 'Sévérité'];
      const rows = filteredIncidents.map(incident => [
        incident.id,
        `"${(incident.titre || '').replace(/"/g, '""')}"`,
        incident.type_menace || '',
        incident.secteur_cible || '',
        incident.source || '',
        incident.created_at ? new Date(incident.created_at).toLocaleDateString('fr-FR') : '',
        `"${(incident.description || '').replace(/"/g, '""')}"`,
        incident.severite || ''
      ]);
      
      const csvContent = [
        headers.join(','),
        ...rows.map(row => row.join(','))
      ].join('\n');
      
      const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      const url = URL.createObjectURL(blob);
      link.setAttribute('href', url);
      link.setAttribute('download', `incidents_${new Date().toISOString().split('T')[0]}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      
      console.log('✅ Export réussi !');
    } catch (error) {
      console.error('❌ Erreur lors de l\'export:', error);
      alert('Erreur lors de l\'export des données');
    }
  };

  // ─────────────────────────────────────────────────────────────
  // 6. RENDU
  // ─────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gold"></div>
        <p className="mt-4 text-textMuted">Chargement des incidents...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh]">
        <div className="bg-alert/10 border border-alert/30 rounded-lg p-6 max-w-md text-center">
          <AlertTriangle className="w-12 h-12 text-alert mx-auto mb-3" />
          <h3 className="text-alert font-semibold">❌ Erreur</h3>
          <p className="text-textMuted mt-2">{error}</p>
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

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8"
    >
      {/* En-tête */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-8">
        <div>
          <h1 className="text-3xl font-display font-bold text-text">Incidents</h1>
          <p className="text-textMuted mt-1">
            {filteredIncidents.length} incident{filteredIncidents.length > 1 ? 's' : ''} trouvé{filteredIncidents.length > 1 ? 's' : ''}
          </p>
        </div>
        <Button onClick={exportData} className="gap-2 bg-gold text-[#0F1B2D] hover:bg-goldLight">
          <Download className="w-4 h-4" />
          Exporter ({filteredIncidents.length})
        </Button>
      </div>

      {/* Filtres */}
      <div className="bg-surface/30 rounded-lg border border-border p-6 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Recherche */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-textMuted" />
            <input
              type="text"
              name="search"
              placeholder="Rechercher..."
              value={filters.search}
              onChange={handleFilterChange}
              className="w-full pl-10 pr-4 py-2 bg-surface border border-border rounded-lg focus:ring-2 focus:ring-gold focus:border-transparent text-text placeholder-textMuted"
            />
          </div>

          {/* Filtre Type */}
          <select
            name="type"
            value={filters.type}
            onChange={handleFilterChange}
            className="px-4 py-2 bg-surface border border-border rounded-lg focus:ring-2 focus:ring-gold focus:border-transparent text-text"
          >
            <option value="">Tous les types</option>
            {types.map((type) => (
              <option key={type} value={type}>{type}</option>
            ))}
          </select>

          {/* Filtre Secteur */}
          <select
            name="secteur"
            value={filters.secteur}
            onChange={handleFilterChange}
            className="px-4 py-2 bg-surface border border-border rounded-lg focus:ring-2 focus:ring-gold focus:border-transparent text-text"
          >
            <option value="">Tous les secteurs</option>
            {sectors.map((sector) => (
              <option key={sector} value={sector}>{sector}</option>
            ))}
          </select>

          {/* Filtre Source */}
          <select
            name="source"
            value={filters.source}
            onChange={handleFilterChange}
            className="px-4 py-2 bg-surface border border-border rounded-lg focus:ring-2 focus:ring-gold focus:border-transparent text-text"
          >
            <option value="">Toutes les sources</option>
            {sources.map((source) => (
              <option key={source} value={source}>{source}</option>
            ))}
          </select>
        </div>

        {/* Filtres Date + Actions */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mt-4">
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <label className="text-sm text-textMuted">Du</label>
              <input
                type="date"
                name="dateFrom"
                value={filters.dateFrom}
                onChange={handleFilterChange}
                className="px-3 py-1.5 bg-surface border border-border rounded-lg focus:ring-2 focus:ring-gold focus:border-transparent text-text text-sm"
              />
            </div>
            <div className="flex items-center gap-2">
              <label className="text-sm text-textMuted">Au</label>
              <input
                type="date"
                name="dateTo"
                value={filters.dateTo}
                onChange={handleFilterChange}
                className="px-3 py-1.5 bg-surface border border-border rounded-lg focus:ring-2 focus:ring-gold focus:border-transparent text-text text-sm"
              />
            </div>
          </div>
          <div className="flex gap-2">
            <Button 
              variant="outline" 
              onClick={resetFilters} 
              className="text-sm border-border text-textMuted hover:bg-surfaceLight"
            >
              <X className="w-4 h-4 mr-1" />
              Réinitialiser
            </Button>
            <Button className="gap-2 text-sm bg-gold text-[#0F1B2D] hover:bg-goldLight">
              <Filter className="w-4 h-4" />
              Appliquer
            </Button>
          </div>
        </div>
      </div>

      {/* Tableau */}
      <div className="bg-surface/30 rounded-lg border border-border overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-surfaceLight/50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-textMuted uppercase tracking-wider">Titre</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-textMuted uppercase tracking-wider">Type</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-textMuted uppercase tracking-wider">Secteur</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-textMuted uppercase tracking-wider">Source</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-textMuted uppercase tracking-wider">Date</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-textMuted uppercase tracking-wider">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {currentIncidents.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center">
                    <div className="flex flex-col items-center">
                      <Search className="w-12 h-12 text-textMuted/30 mb-3" />
                      <p className="text-lg font-medium text-text">Aucun incident trouvé</p>
                      <p className="text-sm text-textMuted">
                        {filters.type || filters.secteur || filters.search ? 
                          'Essayez de modifier vos filtres de recherche' : 
                          'Aucun incident avec un type de menace connu'}
                      </p>
                      {(filters.type || filters.secteur || filters.search) && (
                        <Button 
                          onClick={resetFilters} 
                          variant="outline" 
                          className="mt-4 border-border text-textMuted hover:bg-surfaceLight"
                        >
                          Réinitialiser les filtres
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ) : (
                currentIncidents.map((incident) => (
                  <tr key={incident.id} className="hover:bg-surfaceLight/30 transition-colors">
                    <td className="px-6 py-4 text-sm text-text max-w-xs">
                      <div className="truncate" title={incident.titre}>
                        {incident.titre || 'N/A'}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${getBadgeColor(incident.type_menace)}`}>
                        {incident.type_menace || 'INCONNU'}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-textMuted">
                      {incident.secteur_cible || 'N/A'}
                    </td>
                    <td className="px-6 py-4 text-sm text-textMuted">
                      {incident.source || 'N/A'}
                    </td>
                    <td className="px-6 py-4 text-sm text-textMuted">
                      {incident.created_at ? new Date(incident.created_at).toLocaleDateString('fr-FR') : 'N/A'}
                    </td>
                    <td className="px-6 py-4">
                      <Button variant="ghost" size="sm" className="hover:bg-gold/10 text-textMuted hover:text-gold">
                        <Eye className="w-4 h-4" />
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="px-6 py-4 border-t border-border flex flex-col sm:flex-row justify-between items-center gap-4">
            <p className="text-sm text-textMuted">
              Affichage de {((currentPage - 1) * itemsPerPage) + 1} à {Math.min(currentPage * itemsPerPage, filteredIncidents.length)} sur {filteredIncidents.length} incidents
            </p>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => goToPage(currentPage - 1)}
                disabled={currentPage === 1}
                className="border-border text-textMuted hover:bg-surfaceLight disabled:opacity-50"
              >
                <ChevronLeft className="w-4 h-4" />
              </Button>
              {[...Array(Math.min(5, totalPages))].map((_, index) => {
                const page = index + 1;
                return (
                  <Button
                    key={page}
                    variant={currentPage === page ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => goToPage(page)}
                    className={`w-10 ${currentPage === page ? 'bg-gold text-[#0F1B2D] hover:bg-goldLight' : 'border-border text-textMuted hover:bg-surfaceLight'}`}
                  >
                    {page}
                  </Button>
                );
              })}
              {totalPages > 5 && (
                <>
                  <span className="text-textMuted">...</span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => goToPage(totalPages)}
                    className="w-10 border-border text-textMuted hover:bg-surfaceLight"
                  >
                    {totalPages}
                  </Button>
                </>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={() => goToPage(currentPage + 1)}
                disabled={currentPage === totalPages}
                className="border-border text-textMuted hover:bg-surfaceLight disabled:opacity-50"
              >
                <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
          </div>
        )}
      </div>
    </motion.div>
  );
}