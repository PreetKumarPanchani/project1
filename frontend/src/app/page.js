'use client';

import { useState } from 'react';
import Sidebar from '@/components/Sidebar';
import ChatInterface from '@/components/ChatInterface';

export default function Home() {
  const [activeSection, setActiveSection] = useState('DayseAI');
  
  return (
    <div className="app-container">
      <Sidebar activeSection={activeSection} setActiveSection={setActiveSection} />
      <main className="main-content">
        <ChatInterface />
      </main>
    </div>
  );
}