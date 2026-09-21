import React, { useState, useRef, useEffect } from 'react';

interface AIAnalystPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AIAnalystPanel: React.FC<AIAnalystPanelProps> = ({ isOpen, onClose }) => {
  const panelRef = useRef<HTMLDivElement>(null);
  const LIBRECHAT_URL = 'http://localhost:3080';

  // Handle escape key to close
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);

  // Close when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node) && isOpen) {
        onClose();
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
      <div
        ref={panelRef}
        className="bg-white rounded-lg shadow-2xl w-full max-w-4xl h-[80vh] flex flex-col"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center">
              <span className="text-white text-sm font-bold">AI</span>
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Banking Analyst</h2>
              <p className="text-xs text-gray-500">Powered by ClickHouse MCP</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors p-2"
            aria-label="Close"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content - LibreChat iframe */}
        <div className="flex-1 overflow-hidden">
          <iframe
            src={LIBRECHAT_URL}
            className="w-full h-full border-0"
            title="LibreChat AI Analyst"
            sandbox="allow-same-origin allow-scripts allow-forms allow-popups"
          />
        </div>

        {/* Footer with Quick Prompts */}
        <div className="p-4 border-t border-gray-200 bg-gray-50">
          <p className="text-xs text-gray-500 mb-2 font-medium">Quick Questions:</p>
          <div className="flex flex-wrap gap-2">
            {[
              'Why did transaction failures increase?',
              'Which merchants are most affected?',
              'Show me the gateway health status',
              'What is the current success rate?',
            ].map((prompt) => (
              <button
                key={prompt}
                className="px-3 py-1.5 text-xs bg-white border border-gray-300 rounded-md hover:bg-gray-100 transition-colors text-gray-700"
                onClick={() => {
                  // Note: These are visual prompts - user would need to type them in LibreChat
                  // Future enhancement: could use LibreChat API to pre-fill prompts
                }}
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export const AIAnalystButton: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      {/* Floating Button */}
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 w-14 h-14 bg-blue-600 hover:bg-blue-700 text-white rounded-full shadow-lg flex items-center justify-center transition-all duration-200 hover:scale-110 z-40"
        aria-label="Open AI Analyst"
        title="Ask AI Analyst"
      >
        <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
        </svg>
      </button>

      {/* Panel */}
      <AIAnalystPanel isOpen={isOpen} onClose={() => setIsOpen(false)} />
    </>
  );
};