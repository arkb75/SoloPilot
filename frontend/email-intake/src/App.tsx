import { useState } from 'react';
import ConversationList from './components/ConversationList';
import ConversationDetail from './components/ConversationDetail';
import { Conversation } from './types';

function App() {
  const [selectedConversation, setSelectedConversation] = useState<Conversation | null>(null);

  return (
    <div className="min-h-screen bg-gray-100">
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
          <h1 className="text-3xl font-bold text-gray-900">Email Agent Manager</h1>
        </div>
      </header>

      <main className="py-10">
        <div className="max-w-7xl mx-auto sm:px-6 lg:px-8">
          {selectedConversation ? (
            <ConversationDetail
              conversationId={selectedConversation.conversation_id}
              onBack={() => setSelectedConversation(null)}
            />
          ) : (
            <ConversationList
              onSelectConversation={setSelectedConversation}
            />
          )}
        </div>
      </main>
    </div>
  );
}

export default App;
