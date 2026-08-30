import { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { Send, Bot, User, Loader2, Copy, Sparkles } from 'lucide-react';
import { Card, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/button';
import { sendChat } from '../services/api';  // 🔥 CHANGÉ: utiliser sendChat au lieu de sendChatStream

interface Message {
  role: 'user' | 'bot';
  content: string;
  sources?: string[];
}

// 🔒 Identifiant de session unique par navigateur.
// IMPORTANT : sans ceci, le backend retombe sur session_id='default' pour
// TOUS les visiteurs, ce qui mélange l'historique de conversation de
// personnes différentes dans le même contexte envoyé au LLM (fuite de
// confidentialité entre utilisateurs). Généré une seule fois et persisté
// dans localStorage pour rester stable entre les rechargements de page.
const getSessionId = (): string => {
  const KEY = 'chat_session_id';
  let id = localStorage.getItem(KEY);
  if (!id) {
    id = (typeof crypto !== 'undefined' && crypto.randomUUID)
      ? crypto.randomUUID()
      : `sess_${Date.now()}_${Math.random().toString(36).slice(2)}`;
    localStorage.setItem(KEY, id);
  }
  return id;
};

// 🔥 Suggestions de questions
const SUGGESTIONS = [
  'Comment protéger mon wifi ?',
  'Quelles sont les bonnes pratiques de cybersécurité ?',
  'Que dit le guide sur les sauvegardes ?',
  'Quels sont les incidents dans le secteur bancaire ?',
  "Qu'est-ce que le phishing ?",
];

// 🔒 Échappe les caractères HTML pour empêcher toute injection de balises
// (XSS) : la réponse du bot peut contenir du texte provenant de documents
// indexés ou d'une génération LLM imprévisible, donc jamais de confiance
// aveugle avant dangerouslySetInnerHTML.
const escapeHtml = (str: string) => {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
};

// 🔥 Fonction de formatage sans react-markdown
const formatContent = (content: string) => {
  if (!content) return '';
  // 1) Échapper TOUT le HTML en premier, sur le texte brut.
  let formatted = escapeHtml(content);
  // 2) Puis appliquer le markdown minimal sur le texte déjà échappé :
  //    les balises <strong>/<br /> ajoutées ici sont les nôtres, pas
  //    celles potentiellement présentes dans le contenu source.
  formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  formatted = formatted.replace(/\n/g, '<br />');
  // Nettoyer les caractères de contrôle
  formatted = formatted.replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/g, '');
  return formatted;
};

export default function Chatbot() {
  const [messages, setMessages] = useState<Message[]>(() => {
    const saved = localStorage.getItem('chat_history');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (parsed.length > 0) return parsed;
      } catch (e) {
        // Ignorer les erreurs
      }
    }
    return [{
      role: 'bot',
      content: 'Bonjour. Je suis l\'assistant cyber. Posez-moi une question sur la cybersécurité des PME au Maroc.'
    }];
  });
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    localStorage.setItem('chat_history', JSON.stringify(messages));
  }, [messages]);

  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setInput('');
    setLoading(true);

    try {
      // 🔥 UTILISER sendChat (pas sendChatStream)
      // 🔒 sessionId transmis pour isoler la mémoire de conversation
      // par utilisateur côté backend.
      const response = await sendChat(userMessage, getSessionId());
      console.log('📝 Réponse API reçue:', response);

      if (response && response.response) {
        setMessages(prev => [
          ...prev,
          { 
            role: 'bot', 
            content: response.response,
            sources: response.sources || []
          }
        ]);
      } else {
        setMessages(prev => [
          ...prev,
          { role: 'bot', content: 'Je n\'ai pas trouvé de réponse.' }
        ]);
      }
    } catch (error) {
      console.error('❌ Erreur chat:', error);
      setMessages(prev => [
        ...prev,
        { role: 'bot', content: '❌ Désolé, une erreur est survenue.' }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSuggestionClick = (question: string) => {
    setInput(question);
    textareaRef.current?.focus();
  };

  const copyResponse = (content: string) => {
    navigator.clipboard.writeText(content);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8"
    >
      <h1 className="text-3xl font-bold text-[#E8E4DA] mb-8">Assistant Cyber</h1>

      <Card className="h-[600px] flex flex-col bg-[#0F1B2D] border-[#16243B]">
        <CardContent className="flex-1 p-6 overflow-y-auto">
          <div className="space-y-4">
            {messages.map((msg, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={`flex items-start gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
              >
                <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                  msg.role === 'user' ? 'bg-[#C9932E]' : 'bg-[#16243B]'
                }`}>
                  {msg.role === 'user' ? (
                    <User className="w-4 h-4 text-[#0F1B2D]" />
                  ) : (
                    <Bot className="w-4 h-4 text-[#C9932E]" />
                  )}
                </div>
                <div className={`max-w-[80%] px-4 py-3 rounded-lg ${
                  msg.role === 'user'
                    ? 'bg-[#C9932E] text-[#0F1B2D]'
                    : 'bg-[#16243B] text-[#E8E4DA] border border-[#1E3050]'
                }`}>
                  {msg.role === 'bot' ? (
                    <>
                      <p
                        className="text-sm whitespace-pre-wrap"
                        dangerouslySetInnerHTML={{ __html: formatContent(msg.content) }}
                      />
                      
                      {msg.sources && msg.sources.length > 0 && (
                        <div className="mt-2 pt-2 border-t border-[#1E3050] text-xs text-[#8A8A8A]">
                          <span className="font-medium text-[#C9932E]">📚 Sources :</span>
                          {msg.sources.map((source, i) => (
                            <span key={i} className="ml-2">• {source}</span>
                          ))}
                        </div>
                      )}
                      
                      <button
                        onClick={() => copyResponse(msg.content)}
                        className="mt-2 text-xs text-[#8A8A8A] hover:text-[#C9932E] transition-colors flex items-center gap-1"
                      >
                        <Copy className="w-3 h-3" />
                        Copier
                      </button>
                    </>
                  ) : (
                    <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                  )}
                </div>
              </motion.div>
            ))}
            
            {loading && (
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-full bg-[#16243B] flex items-center justify-center">
                  <Bot className="w-4 h-4 text-[#C9932E]" />
                </div>
                <div className="bg-[#16243B] px-4 py-3 rounded-lg border border-[#1E3050]">
                  <div className="flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin text-[#C9932E]" />
                    <span className="text-sm text-[#8A8A8A]">Génération de la réponse...</span>
                  </div>
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>
        </CardContent>

        {messages.length === 1 && !loading && (
          <div className="px-4 pb-2 flex flex-wrap gap-2">
            <div className="w-full mb-1 text-xs text-[#8A8A8A] flex items-center gap-1">
              <Sparkles className="w-3 h-3" />
              Suggestions :
            </div>
            {SUGGESTIONS.map((suggestion, i) => (
              <button
                key={i}
                onClick={() => handleSuggestionClick(suggestion)}
                className="text-xs px-3 py-1 bg-[#16243B] text-[#8A8A8A] rounded-full border border-[#1E3050] hover:border-[#C9932E] hover:text-[#C9932E] transition-colors"
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}

        <div className="border-t border-[#16243B] p-4 bg-[#0F1B2D]">
          <div className="flex gap-3">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Posez votre question..."
              className="flex-1 px-4 py-2 bg-[#16243B] text-[#E8E4DA] border border-[#1E3050] rounded-lg resize-none focus:ring-2 focus:ring-[#C9932E] focus:border-transparent placeholder-[#8A8A8A] text-sm"
              rows={2}
              disabled={loading}
            />
            <Button 
              onClick={handleSend} 
              disabled={loading} 
              className="self-end bg-[#C9932E] hover:bg-[#B8860B] text-[#0F1B2D] px-4 py-2 rounded-lg"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            </Button>
          </div>
        </div>
      </Card>
    </motion.div>
  );
}