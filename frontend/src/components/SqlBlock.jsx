const KEYWORDS = new Set([
  'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'NOT', 'IN', 'LIKE', 'IS', 'NULL', 'AS',
  'JOIN', 'INNER', 'LEFT', 'RIGHT', 'OUTER', 'ON', 'GROUP', 'ORDER', 'BY', 'HAVING',
  'LIMIT', 'OFFSET', 'DISTINCT', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'UNION', 'ALL',
  'EXISTS', 'BETWEEN', 'ASC', 'DESC', 'WITH', 'INTO', 'VALUES', 'INSERT', 'UPDATE', 'SET',
])

const FUNCTIONS = new Set([
  'COUNT', 'SUM', 'AVG', 'MAX', 'MIN', 'ROUND', 'COALESCE', 'CAST', 'STRFTIME',
  'LOWER', 'UPPER', 'SUBSTR', 'LENGTH', 'IFNULL', 'ABS',
])

// Tokenizes into strings / numbers / identifiers-or-keywords / everything else (kept as-is
// so punctuation, whitespace and newlines render exactly like the original SQL).
const TOKEN_RE = /('(?:[^'\\]|\\.)*')|(\b\d+\.?\d*\b)|([A-Za-z_][A-Za-z0-9_]*)/g

export default function SqlBlock({ sql }) {
  if (!sql) return null

  const nodes = []
  let lastIndex = 0
  let key = 0
  let match

  while ((match = TOKEN_RE.exec(sql)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(sql.slice(lastIndex, match.index))
    }
    const [full, stringLit, number, word] = match
    if (stringLit) {
      nodes.push(<span className="sql-tok-string" key={key++}>{stringLit}</span>)
    } else if (number) {
      nodes.push(<span className="sql-tok-number" key={key++}>{number}</span>)
    } else if (word) {
      const upper = word.toUpperCase()
      if (KEYWORDS.has(upper)) {
        nodes.push(<span className="sql-tok-keyword" key={key++}>{word}</span>)
      } else if (FUNCTIONS.has(upper)) {
        nodes.push(<span className="sql-tok-function" key={key++}>{word}</span>)
      } else {
        nodes.push(word)
      }
    } else {
      nodes.push(full)
    }
    lastIndex = match.index + full.length
  }
  if (lastIndex < sql.length) {
    nodes.push(sql.slice(lastIndex))
  }

  return <pre className="sql-block">{nodes}</pre>
}
