# BigQuery Query Analyzer

A comprehensive tool for analyzing and optimizing BigQuery SQL queries to improve performance and reduce costs.

## Overview

The BigQuery Query Analyzer is a web application that helps data engineers and analysts identify anti-patterns in their SQL queries and provides optimized alternatives. It uses a combination of rule-based analysis and AI-powered recommendations to detect potential performance issues in your BigQuery queries.

## Features

- **Query Analysis**: Identify common BigQuery anti-patterns in your SQL queries
- **Query Optimization**: Get optimized versions of your queries with explanatory comments
- **Slow Query Monitoring**: View and filter slow-running queries
- **AI-Powered Recommendations**: Get intelligent optimization suggestions using Claude AI (when configured)
- **Detailed Explanations**: Understand why certain patterns are problematic and how to fix them

## Supported Anti-Patterns

The analyzer can detect and fix several common BigQuery anti-patterns:

1. **SELECT * without EXCEPT**: Using `SELECT *` is cost inefficient; use specific columns or `SELECT * EXCEPT`
2. **Multiple WITH clause references**: Multiple references to the same WITH clause can lead to query plan explosion
3. **Subqueries in filters without DISTINCT**: Subqueries in WHERE clauses should use DISTINCT when appropriate
4. **ORDER BY without LIMIT**: Can cause Resources Exceeded errors for large result sets
5. **REGEXP_CONTAINS for simple patterns**: Using LIKE is faster for simple pattern matching
6. **Suboptimal JOIN order**: Placing smaller tables before larger tables can reduce performance

## How It Works

### Query Analysis Flow

When you select a query for analysis, the following process occurs:

#### Step 1: User Selects a Query for Analysis

When you click on the "Analyze" button for a specific query in the slow queries list, your browser makes a GET request to the `/analyze` endpoint with a query parameter containing the query ID:

```
GET /analyze?query_id=1
```

#### Step 2: FastAPI Route Handler is Triggered

The `analyze_page` function in `app.py` handles this request:

```python
@app.get("/analyze", response_class=HTMLResponse)
async def analyze_page(request: Request, query_id: Optional[str] = None):
    """Render the analysis page"""
    if query_id:
        # Get query by ID using the MCP tool
        query = get_query_by_id(query_id)
        
        if query:
            # Analyze the query using the MCP tool
            analysis = analyze_query(query["query_text"])
            
            return templates.TemplateResponse("analyze.html", {
                "request": request, 
                "analysis": analysis,
                "query_id": query_id
            })
```

#### Step 3: MCP Tool Retrieves the Query

The `get_query_by_id` MCP tool is called with the query ID:

```python
query = get_query_by_id(query_id)
```

This tool searches through the database (or mock data) to find the query with the matching ID and returns its details.

#### Step 4: MCP Tool Analyzes the Query

The `analyze_query` MCP tool is called with the query text:

```python
analysis = analyze_query(query["query_text"])
```

This function performs the following steps:

1. **BigQuery-specific Analysis**:
   - First, it uses the BigQuery anti-patterns module to check for common issues
   - It analyzes the query structure using regex patterns and heuristics

2. **LLM Analysis Attempt** (if available):
   - If configured, it will use Claude AI to analyze the query
   - The LLM integration makes an API call to Anthropic's Claude
   - It sends the query text along with instructions to analyze for SQL anti-patterns
   - Claude returns a JSON response with analysis results and explanations

3. **Fallback to Rule-Based Analysis** (if LLM fails):
   - If Claude is not available or fails, it falls back to rule-based analysis
   - This uses regex patterns to detect common SQL anti-patterns

#### Step 5: Template Rendering

Once analysis is complete, the results are passed to the template renderer:

```python
return templates.TemplateResponse("analyze.html", {
    "request": request, 
    "analysis": analysis,
    "query_id": query_id
})
```

The Jinja2 template engine processes `analyze.html` and injects the analysis results.

#### Step 6: HTML Response

The rendered HTML is sent back to the browser, displaying:

1. **The Original Query**: Shown in a formatted code block
2. **Analysis Results Table**: A table showing:
   - Each potential anti-pattern (SELECT *, multiple WITH clauses, etc.)
   - Status (Issue Detected or OK)
   - Description/explanation of the issue

#### Step 7: User Interaction

From here, you can:
- View the detailed analysis
- Request query optimization by clicking the "Get Optimization Suggestions" button
- Go back to the query list or submit a different query

### Behind the Scenes: MCP Tools Framework

The MCP (Model Context Protocol) Tools framework provides a structured approach for these operations:

- Each function is wrapped with `@mcp.tool()` to register it as a tool
- Documentation is automatically generated from the function docstrings
- Each tool has a clear purpose and interface
- Tools can be called by name from different parts of the application

This structure makes the application more maintainable and easier to extend with new analysis techniques or data sources in the future.

## Installation

### Prerequisites

- Python 3.7+
- pip
- An Anthropic API key (optional, for AI-powered recommendations)

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/bigquery-query-analyzer.git
   cd bigquery-query-analyzer
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables (optional, for AI features):
   ```bash
   cp .env.example .env
   # Edit .env with your Anthropic API key
   ```

4. Run the application:
   ```bash
   ./run_app.sh
   ```

5. Access the web interface at http://localhost:8000

## Usage

1. **View Slow Queries**: Navigate to the "Slow Queries" section to see a list of slow-running queries
2. **Analyze a Query**:
   - Click "Analyze" on any query in the list, or
   - Go to the "Analyze" page and enter your SQL query
3. **Optimize a Query**:
   - After analysis, click "Get Optimization Suggestions" to see an optimized version
   - The optimized query includes explanatory comments for all changes made

## Configuration

The application can be configured using environment variables:

- `ANTHROPIC_API_KEY`: Your Anthropic API key for using Claude AI
- `ANTHROPIC_MODEL`: The Claude model to use (default: claude-3-haiku-20240307)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.