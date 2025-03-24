'use client';

import { useEffect, useRef } from 'react';

const SqlDisplay = ({ query }) => {
  const queryRef = useRef(null);

  useEffect(() => {
    if (!query || !queryRef.current) return;
    
    // Basic SQL syntax highlighting
    const keywords = [
      'SELECT', 'FROM', 'WHERE', 'ORDER BY', 'GROUP BY', 'JOIN', 
      'LEFT JOIN', 'RIGHT JOIN', 'INNER JOIN', 'OUTER JOIN', 'ON', 
      'AS', 'AND', 'OR', 'NOT', 'IN', 'LIKE', 'BETWEEN', 'IS NULL', 
      'IS NOT NULL', 'COUNT', 'SUM', 'AVG', 'MAX', 'MIN', 'HAVING', 
      'LIMIT', 'OFFSET', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 
      'ALTER', 'DROP', 'TABLE', 'VIEW', 'INDEX', 'DISTINCT', 'ASC', 'DESC'
    ];
    
    // Replace SQL keywords with highlighted spans
    let highlightedQuery = query;
    keywords.forEach(keyword => {
      // Use regex to match whole words only and case insensitive
      const regex = new RegExp('\\b' + keyword + '\\b', 'gi');
      highlightedQuery = highlightedQuery.replace(regex, match => {
        return `<span class="keyword">${match}</span>`;
      });
    });
    
    // Highlight numbers
    highlightedQuery = highlightedQuery.replace(/\b\d+\b/g, '<span class="number">$&</span>');
    
    // Highlight strings (text between quotes)
    highlightedQuery = highlightedQuery.replace(/'([^']*)'/g, '\'<span class="string">$1</span>\'');
    
    queryRef.current.innerHTML = highlightedQuery;
  }, [query]);

  if (!query) return null;

  return (
    <div className="sql-container">
      <h4>Query:</h4>
      <pre ref={queryRef} className="sql-query"></pre>
    </div>
  );
};

export default SqlDisplay;