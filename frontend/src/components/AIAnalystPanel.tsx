import React from 'react';

const LIBRECHAT_URL = 'http://localhost:3080';

export const AIAnalystButton: React.FC = () => {
  const openAIAnalyst = () => {
    window.open(LIBRECHAT_URL, '_blank');
  };

  return (
    <button
      onClick={openAIAnalyst}
      className="fixed bottom-6 right-6 w-14 h-14 bg-blue-600 hover:bg-blue-700 text-white rounded-full shadow-lg flex items-center justify-center transition-all duration-200 hover:scale-110 z-40"
      aria-label="Open AI Analyst"
      title="Ask AI Analyst - Opens LibreChat in new tab"
    >
      <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
      </svg>
    </button>
  );
};