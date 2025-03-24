'use client';

const ExampleQueries = ({ onSelectQuery }) => {
  // Sample queries from the original application
  const queries = [
    "Show all customers",
    "Show orders by status",
    "Show popular product",
    "Count customers",
    "Show recent orders",
    "Status of Order 40",
    "Value of Order 40"
  ];

  return (
    <div className="queries-grid">
      {queries.map((query, index) => (
        <div 
          key={index} 
          className="query-card"
          onClick={() => onSelectQuery(query)}
        >
          {query}
        </div>
      ))}
    </div>
  );
};

export default ExampleQueries;