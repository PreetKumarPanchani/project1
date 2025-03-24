'use client';
import { useState } from 'react';

const Sidebar = ({ activeSection, setActiveSection }) => {
  const [activeSecondary, setActiveSecondary] = useState(null);
  
  const navItems = [
    { id: 'DayseAI', label: 'DayseAI' },
    //{ id: 'ASTTERI', label: 'ASTTERI' },
    //{ id: 'QubeChain', label: 'QubeChain' }
  ];
  
  const secondaryItems = [
    { id: 'suggestions', label: 'Suggestions', icon: 'bi-lightbulb' },
    { id: 'database', label: 'Data base', icon: 'bi-database' }
  ];

  const handleSecondaryClick = (id) => {
    setActiveSecondary(activeSecondary === id ? null : id);
  };

  return (
    <aside className="sidebar">
      <div className="logo">
        <img src="/images/LQ_Icon.png" alt="Logo" className="logo-image" />
        <span className="logo-text">LIQUIDQUBE</span>
      </div>
      
      {/* Main navigation */}
      <div className="main-nav">
        {navItems.map(item => (
          <div
            key={item.id}
            className={`nav-item ${activeSection === item.id ? 'active' : ''}`}
            onClick={() => setActiveSection(item.id)}
          >
            {item.label}
          </div>
        ))}
      </div>
      
      {/* Secondary navigation with fixed position */}
      <div className="secondary-nav">
        {secondaryItems.map(item => (
          <div
            key={item.id}
            className={`nav-item ${activeSecondary === item.id ? 'active' : ''}`}
            onClick={() => handleSecondaryClick(item.id)}
          >
            <i className={`bi ${item.icon} me-2`}></i>
            {item.label}
          </div>
        ))}
      </div>
    </aside>
  );
};

export default Sidebar;