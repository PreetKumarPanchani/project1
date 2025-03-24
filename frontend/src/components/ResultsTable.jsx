'use client';

const ResultsTable = ({ results }) => {
  if (!results || results.length === 0) return null;

  // Get headers from first result
  const headers = Object.keys(results[0]);

  // Format value based on type
  const formatValue = (value) => {
    if (value === null || value === undefined) return 'NULL';
    
    if (typeof value === 'number') {
      // Format numbers with commas for thousands and 2 decimal places if needed
      return value % 1 === 0 
        ? value.toLocaleString() 
        : value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    
    if (value instanceof Date) {
      return value.toLocaleString();
    }
    
    return String(value);
  };

  return (
    <div className="results-container">
      <h4>Results:</h4>
      <div className="table-wrapper">
        <table className="results-table">
          <thead>
            <tr>
              {headers.map((header, index) => (
                <th key={index}>{header}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {results.map((row, rowIndex) => (
              <tr key={rowIndex}>
                {headers.map((header, cellIndex) => (
                  <td key={cellIndex}>{formatValue(row[header])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {/* Summary of results hide it for now */}
      {/* <div className="results-summary" >
        {results.length} {results.length === 1 ? 'row' : 'rows'} returned
      </div> */}
    </div>
  );
};

export default ResultsTable;