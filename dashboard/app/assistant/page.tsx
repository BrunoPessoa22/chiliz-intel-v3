'use client';

import { useState, useRef, useEffect } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  data?: any;
}

interface SuggestedQuestion {
  category: string;
  questions: string[];
}

export default function AssistantPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<SuggestedQuestion[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchSuggestions();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function fetchSuggestions() {
    try {
      const res = await fetch(`${API_URL}/api/assistant/suggested-questions`);
      const data = await res.json();
      setSuggestions(data.suggestions || []);
    } catch (error) {
      console.error('Failed to fetch suggestions:', error);
    }
  }

  async function sendMessage(content: string) {
    if (!content.trim() || loading) return;

    const userMessage: Message = {
      role: 'user',
      content,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/api/assistant/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: content,
          session_id: sessionId,
        }),
      });

      const data = await res.json();

      if (!sessionId) {
        setSessionId(data.session_id);
      }

      const assistantMessage: Message = {
        role: 'assistant',
        content: data.response,
        timestamp: new Date(),
        data: data.data,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Failed to send message:', error);
      const errorMessage: Message = {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyPress(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-120px)]">
      {/* Header */}
      <div className="mb-4">
        <h1 className="text-3xl font-bold">AI Management Assistant</h1>
        <p className="text-gray-400">Ask questions about fan token performance, health, and market conditions</p>
      </div>

      {/* Chat Container */}
      <div className="flex-1 flex gap-6 overflow-hidden">
        {/* Messages Area */}
        <div className="flex-1 flex flex-col bg-chiliz-dark rounded-xl border border-gray-800 overflow-hidden">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-5xl mb-4">🤖</p>
                <h2 className="text-xl font-medium mb-2">Hello! I'm your AI Assistant</h2>
                <p className="text-gray-400 max-w-md mx-auto">
                  I can help you understand fan token performance, analyze market conditions,
                  and provide executive insights. Ask me anything!
                </p>
              </div>
            ) : (
              messages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] rounded-lg p-4 ${
                      msg.role === 'user'
                        ? 'bg-chiliz-red text-white'
                        : 'bg-gray-800 text-gray-100'
                    }`}
                  >
                    <div className="whitespace-pre-wrap">{msg.content}</div>
                    {msg.data && (
                      <div className="mt-3 p-3 bg-black/30 rounded text-sm overflow-x-auto">
                        <pre>{JSON.stringify(msg.data, null, 2)}</pre>
                      </div>
                    )}
                    <p className="text-xs opacity-50 mt-2">
                      {msg.timestamp.toLocaleTimeString()}
                    </p>
                  </div>
                </div>
              ))
            )}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-gray-800 rounded-lg p-4">
                  <div className="flex gap-1">
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <div className="border-t border-gray-800 p-4">
            <div className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Ask about fan token performance, health scores, liquidity..."
                className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-400 focus:outline-none focus:border-chiliz-red"
                disabled={loading}
              />
              <button
                onClick={() => sendMessage(input)}
                disabled={loading || !input.trim()}
                className="bg-chiliz-red hover:bg-red-700 disabled:bg-gray-700 disabled:cursor-not-allowed px-6 py-3 rounded-lg font-medium transition"
              >
                Send
              </button>
            </div>
          </div>
        </div>

        {/* Suggestions Sidebar */}
        <div className="w-80 bg-chiliz-dark rounded-xl border border-gray-800 p-4 overflow-y-auto">
          <h3 className="font-bold mb-4">Suggested Questions</h3>
          <div className="space-y-4">
            {suggestions.map((cat, idx) => (
              <div key={idx}>
                <p className="text-xs text-gray-400 uppercase tracking-wide mb-2">
                  {cat.category}
                </p>
                <div className="space-y-2">
                  {cat.questions.map((q, qIdx) => (
                    <button
                      key={qIdx}
                      onClick={() => sendMessage(q)}
                      disabled={loading}
                      className="w-full text-left text-sm bg-gray-800/50 hover:bg-gray-800 p-3 rounded-lg transition text-gray-300 hover:text-white"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
