import { useState } from 'react';
import './App.css';
import NewHomepage from './NewHomepage';
import ConsumerPage from './ConsumerPage';

export default function App() {
  const [view, setView] = useState('consumer'); // 'consumer' or 'home'

  return (
    <main className="shell">
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginBottom: 12 }}>
        <button className={`tab-button ${view === 'home' ? 'active' : ''}`} type="button" onClick={() => setView('home')}>홈페이지</button>
        <button className={`tab-button ${view === 'consumer' ? 'active' : ''}`} type="button" onClick={() => setView('consumer')}>소비자 페이지</button>
      </div>

      {view === 'home' ? (
        <NewHomepage onAnalyze={() => setView('consumer')} />
      ) : (
        <ConsumerPage />
      )}
    </main>
  );
}
