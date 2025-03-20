# BigQuery Query Analyzer - MCP Server Implementation

This project implements a Model Context Protocol (MCP) server for analyzing and optimizing BigQuery SQL queries. The server provides tools to identify slow queries, analyze SQL anti-patterns, and generate optimized query suggestions.

## Core Concepts

This implementation follows the core concepts of the Model Context Protocol (MCP) as described in the [Python SDK](https://github.com/modelcontextprotocol/python-sdk#core-concepts).

- **MCP Server**: The main server that processes incoming MCP contexts and returns responses.
- **MCP Model**: The implementation of the core logic for query analysis.
- **MCP Context**: Contains the actions and parameters for each request.
- **MCP Action**: Specific operations that can be performed by the server.
- **MCP Response**: The results returned from processing MCP contexts.

## Features

The server provides three main tools:

1. **Get Slow Queries**: Retrieves a list of slow queries from a mock BigQuery database, with filtering options for runtime and user.
2. **Analyze Queries**: Identifies SQL anti-patterns, such as:
   - Using `SELECT *` without `EXCEPT`
   - Multiple `WITH` clauses
   - Subqueries with aggregation
   - Subqueries with `DISTINCT`
   - Too many joins
   - `ORDER BY` without `LIMIT`
3. **Query Optimization**: Provides optimized versions of queries based on identified issues.

## Project Structure

- `mcp_server.py`: The core MCP server implementation with the query analysis model
- `mcp_client.py`: A client script to interact with the MCP server
- `web_interface.py`: A FastAPI web application to interact with the MCP server through a UI
- `templates/`: HTML templates for the web interface

## Usage Examples

### Using the MCP Server Directly

```python
from mcp_server import BigQueryAnalysisServer
from mcp import MCPContext, MCPAction
import asyncio
import json

async def example():
    server = BigQueryAnalysisServer()
    
    # Get slow queries with min_runtime filter
    context = MCPContext(
        actions=[MCPAction(name="get_slow_queries", parameters={"min_runtime": 50000})]
    )
    response = await server.process(context)
    slow_queries = json.loads(response.content)
    print(f"Found {len(slow_queries)} slow queries")
    
    # Analyze a specific query
    context = MCPContext(
        actions=[MCPAction(name="analyze_query", parameters={"query_id": "5"})]
    )
    response = await server.process(context)
    analysis = json.loads(response.content)
    print(f"Analysis found {sum(analysis['analysis'].values())} issues")
    
    # Optimize a query
    context = MCPContext(
        actions=[MCPAction(name="optimize_query", parameters={
            "query_text": "SELECT * FROM large_table WHERE date > '2023-01-01'"
        })]
    )
    response = await server.process(context)
    optimization = json.loads(response.content)
    print(f"Optimized query: {optimization['optimized_query']}")

# Run the example
asyncio.run(example())
```

### Using the Client Script

```bash
python mcp_client.py
```

### Running the Web Interface

```bash
python app.py
```

Then navigate to http://localhost:8000 in your web browser.

## Anti-Pattern Detection

The system identifies several common BigQuery SQL anti-patterns:

1. **SELECT * Without EXCEPT**:
   - Problem: Retrieves unnecessary columns, increasing I/O and network usage
   - Solution: Specify only needed columns or use `SELECT * EXCEPT (col1, col2)`

2. **Multiple WITH Clauses**:
   - Problem: Can make query optimization difficult
   - Solution: Consolidate related WITH clauses or use temporary tables

3. **Subqueries with Aggregation**:
   - Problem: Inefficient data processing, especially with large datasets
   - Solution: Use JOINs with pre-aggregated tables

4. **Subqueries with DISTINCT**:
   - Problem: Expensive operation, especially within subqueries
   - Solution: Replace with EXISTS or GROUP BY

5. **Too Many Joins**:
   - Problem: Performance degradation with multiple joins
   - Solution: Consider denormalizing or using materialized views

6. **ORDER BY Without LIMIT**:
   - Problem: Sorts the entire result set even if only a few rows are needed
   - Solution: Add a LIMIT clause to improve performance

## Future Enhancements

- Connect to actual BigQuery for real query analysis
- Expand anti-pattern detection rules
- Improve optimization suggestions with query-specific context
- Add query execution time estimation
- Implement user authentication and query history tracking

## Requirements

- Python 3.7+
- FastAPI
- MCP SDK
- Uvicorn
- Jinja2

## Installation

```bash
pip install mcp fastapi uvicorn jinja2
```

## License

MIT License
