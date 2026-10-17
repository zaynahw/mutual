import React from 'react';
import ReactDOM from 'react-dom/client';
import './style.css';

function App() {
  const [health, setHealth] = React.useState('Not checked');
  async function checkHealth() {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/health`);
      if (!response.ok) throw new Error('Health check failed');
      const data = await response.json() as { status: string };
      setHealth(data.status);
    } catch { setHealth('Backend unavailable'); }
  }
  return <main className="min-h-screen bg-stone-50 p-10 text-stone-900">
    <div className="mx-auto max-w-xl space-y-6">
      <p className="text-sm font-semibold uppercase tracking-widest text-teal-700">Hackathon scaffold · Demo only</p>
      <h1 className="text-5xl font-bold">Mutual</h1>
      <p>Two personal agents. A plan that feels comfortable for both people.</p>
      <p className="text-stone-600">Scheduling and approval screens will be built in the frontend lane. Both people must approve before a calendar event is created.</p>
      <button onClick={checkHealth} className="rounded-lg bg-teal-800 px-5 py-3 text-white">Check backend health</button>
      <p role="status">Backend: {health}</p>
    </div>
  </main>;
}
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>);
