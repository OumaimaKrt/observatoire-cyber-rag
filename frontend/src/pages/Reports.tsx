// frontend/src/pages/Reports.tsx
import { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { FileText, Download, Printer, Calendar, Building2, TrendingUp, AlertTriangle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { Button } from '../components/ui/button';
import { getSectors, getSectorReport } from '../services/api';
import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';

interface ReportData {
  secteur: string;
  total_incidents: number;
  critiques: number;
  ransomwares: number;
  phishing: number;
  top_menaces: { type: string; count: number }[];
}

const extractData = (response: any, fallback: any = null) => {
  if (!response) return fallback;
  if (response.data !== undefined && response.data !== null) {
    return response.data;
  }
  return response || fallback;
};

export default function Reports() {
  const [sectors, setSectors] = useState<string[]>([]);
  const [selectedSector, setSelectedSector] = useState('');
  const [report, setReport] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  
  const reportRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fetchSectors = async () => {
      try {
        const response = await getSectors();
        const sectorsData = extractData(response, []);
        const filteredSectors = sectorsData.filter((s: string) => s !== 'INCONNU' && s !== '');
        setSectors(filteredSectors);
        setError(null);
      } catch (error) {
        console.error('Erreur chargement secteurs:', error);
        setError('Impossible de charger la liste des secteurs');
        setSectors([]);
      }
    };
    fetchSectors();
  }, []);

  const handleGenerateReport = async () => {
    if (!selectedSector) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const response = await getSectorReport(selectedSector);
      const reportData = extractData(response, null);
      
      if (reportData) {
        setReport(reportData);
      } else {
        setError('Aucune donnée disponible pour ce secteur');
        setReport(null);
      }
    } catch (error) {
      console.error('Erreur génération rapport:', error);
      setError('Erreur lors de la génération du rapport');
      setReport(null);
    } finally {
      setLoading(false);
    }
  };

  // 🔥 EXPORT PDF
  const exportPDF = async () => {
    if (!reportRef.current) return;
    
    setExporting(true);
    
    try {
      const canvas = await html2canvas(reportRef.current, {
        scale: 2,
        backgroundColor: '#0F1B2D',
        allowTaint: true,
        useCORS: true,
      });
      
      const imgData = canvas.toDataURL('image/png');
      const pdf = new jsPDF('p', 'mm', 'a4');
      const pdfWidth = pdf.internal.pageSize.getWidth();
      const pdfHeight = (canvas.height * pdfWidth) / canvas.width;
      
      pdf.addImage(imgData, 'PNG', 0, 0, pdfWidth, pdfHeight);
      pdf.save(`rapport_${report?.secteur || 'secteur'}_${new Date().toISOString().split('T')[0]}.pdf`);
      
    } catch (error) {
      console.error('❌ Erreur export PDF:', error);
      alert('Erreur lors de l\'export PDF');
    } finally {
      setExporting(false);
    }
  };

  // 🔥 EXPORT CSV
  const exportCSV = () => {
    if (!report) return;
    
    try {
      const headers = ['Secteur', 'Total Incidents', 'Critiques', 'Ransomwares', 'Phishing'];
      const rows = [
        [
          report.secteur,
          report.total_incidents,
          report.critiques,
          report.ransomwares,
          report.phishing
        ]
      ];
      
      if (report.top_menaces && report.top_menaces.length > 0) {
        headers.push('Top Menaces');
        rows[0].push(
          report.top_menaces.map(m => `${m.type} (${m.count})`).join('; ')
        );
      }
      
      const csvContent = [
        headers.join(','),
        ...rows.map(row => row.join(','))
      ].join('\n');
      
      const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      const url = URL.createObjectURL(blob);
      link.setAttribute('href', url);
      link.setAttribute('download', `rapport_${report.secteur}_${new Date().toISOString().split('T')[0]}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      
    } catch (error) {
      console.error('❌ Erreur export CSV:', error);
      alert('Erreur lors de l\'export CSV');
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8"
    >
      <h1 className="text-3xl font-display font-bold text-text mb-8">Rapports sectoriels</h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
          <Card className="border-border bg-surface/30">
            <CardHeader>
              <CardTitle className="text-text text-lg">Générer un rapport</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-textMuted mb-2">
                  Secteur
                </label>
                <select
                  value={selectedSector}
                  onChange={(e) => setSelectedSector(e.target.value)}
                  className="w-full px-4 py-2 bg-surface border border-border rounded-lg focus:ring-2 focus:ring-gold focus:border-transparent text-text"
                >
                  <option value="">Choisir un secteur</option>
                  {sectors.map((sector) => (
                    <option key={sector} value={sector}>{sector}</option>
                  ))}
                </select>
              </div>

              {error && (
                <div className="bg-alert/10 border border-alert/30 rounded-lg p-3 text-alert text-sm">
                  <AlertTriangle className="w-4 h-4 inline mr-2" />
                  {error}
                </div>
              )}

              <Button
                onClick={handleGenerateReport}
                disabled={!selectedSector || loading}
                className="w-full gap-2 bg-gold text-[#0F1B2D] hover:bg-goldLight disabled:opacity-50"
              >
                {loading ? (
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-[#0F1B2D]"></div>
                ) : (
                  <>
                    <FileText className="w-4 h-4" />
                    Générer le rapport
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        </div>

        <div className="lg:col-span-2">
          {report ? (
            <Card className="border-border bg-surface/30">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="text-text text-lg">
                  Rapport - <span className="text-gold">{report.secteur}</span>
                </CardTitle>
                <div className="flex gap-2">
                  <Button 
                    variant="outline" 
                    size="sm" 
                    className="gap-2 border-border text-textMuted hover:bg-surfaceLight"
                    onClick={() => window.print()}
                  >
                    <Printer className="w-4 h-4" />
                    Imprimer
                  </Button>
                  <Button 
                    variant="outline" 
                    size="sm" 
                    className="gap-2 border-border text-textMuted hover:bg-surfaceLight"
                    onClick={exportPDF}
                    disabled={exporting}
                  >
                    {exporting ? (
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-gold"></div>
                    ) : (
                      <Download className="w-4 h-4" />
                    )}
                    {exporting ? 'Export...' : 'PDF'}
                  </Button>
                  <Button 
                    variant="outline" 
                    size="sm" 
                    className="gap-2 border-border text-textMuted hover:bg-surfaceLight"
                    onClick={exportCSV}
                  >
                    <FileText className="w-4 h-4" />
                    CSV
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div ref={reportRef}>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                    <div className="bg-surface/50 p-4 rounded-lg text-center border border-border">
                      <div className="text-2xl font-bold text-gold">{report.total_incidents || 0}</div>
                      <div className="text-sm text-textMuted">Total incidents</div>
                    </div>
                    <div className="bg-surface/50 p-4 rounded-lg text-center border border-border">
                      <div className="text-2xl font-bold text-alert">{report.critiques || 0}</div>
                      <div className="text-sm text-textMuted">Critiques</div>
                    </div>
                    <div className="bg-surface/50 p-4 rounded-lg text-center border border-border">
                      <div className="text-2xl font-bold text-purple-400">{report.ransomwares || 0}</div>
                      <div className="text-sm text-textMuted">Ransomwares</div>
                    </div>
                    <div className="bg-surface/50 p-4 rounded-lg text-center border border-border">
                      <div className="text-2xl font-bold text-orange-400">{report.phishing || 0}</div>
                      <div className="text-sm text-textMuted">Phishing</div>
                    </div>
                  </div>

                  <h3 className="font-semibold text-text mb-3 flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-gold" />
                    Top menaces
                  </h3>
                  {report.top_menaces && report.top_menaces.length > 0 ? (
                    <ul className="space-y-2">
                      {report.top_menaces.map((item, idx) => (
                        <li 
                          key={idx} 
                          className="flex justify-between items-center border-b border-border py-2 text-textMuted hover:text-text transition-colors"
                        >
                          <span>{item.type}</span>
                          <span className="font-semibold text-gold">{item.count}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-textMuted text-sm">Aucune menace recensée</p>
                  )}
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card className="h-full flex items-center justify-center border-border bg-surface/30">
              <CardContent className="text-center py-12">
                <FileText className="w-16 h-16 text-textMuted/30 mx-auto mb-4" />
                <p className="text-textMuted">
                  {loading ? 'Génération du rapport...' : 'Sélectionnez un secteur et générez un rapport'}
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </motion.div>
  );
}