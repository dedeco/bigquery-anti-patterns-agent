from typing import Dict, List, Any, Optional
from fastapi import FastAPI, Request, Form, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import os
import re
import json
from mcp.server.fastmcp import FastMCP
from llm_integration import LLMQueryAnalyzer
from starlette.middleware.sessions import SessionMiddleware

# Set up FastMCP
mcp = FastMCP("BigQuery Query Analyzer")
app = FastAPI(title="BigQuery Query Analyzer")
app.add_middleware(SessionMiddleware, secret_key="your-secret-key")
templates = Jinja2Templates(directory="templates")

# Mock BigQuery data - this would typically come from a real database
MOCK_QUERY_DATA = [
    {
        "query_id": "1",
        "query_text": "SELECT * FROM sales_data WHERE date > '2023-01-01'",
        "runtime_ms": 15000,
        "user": "analyst1",
        "timestamp": "2023-03-15T14:25:10",
        "bytes_processed": 250000000
    },
    {
        "query_id": "2",
        "query_text": """
        WITH customer_orders AS (
            SELECT customer_id, COUNT(DISTINCT order_id) as order_count
            FROM orders
            GROUP BY customer_id
        ),
        customer_items AS (
            SELECT customer_id, COUNT(DISTINCT item_id) as item_count
            FROM order_items
            GROUP BY customer_id
        )
        SELECT c.*, co.order_count, ci.item_count
        FROM customers c
        LEFT JOIN customer_orders co ON c.customer_id = co.customer_id
        LEFT JOIN customer_items ci ON c.customer_id = ci.customer_id
        WHERE c.region = 'NORTH'
        """,
        "runtime_ms": 45000,
        "user": "analyst2",
        "timestamp": "2023-03-16T10:15:22",
        "bytes_processed": 750000000
    },
    {
        "query_id": "3",
        "query_text": """
        SELECT 
            date, 
            store_id, 
            SUM(amount) as total_sales,
            COUNT(DISTINCT customer_id) as unique_customers
        FROM sales_data
        WHERE date BETWEEN '2023-01-01' AND '2023-01-31'
        GROUP BY date, store_id
        HAVING SUM(amount) > 1000
        ORDER BY date, total_sales DESC
        """,
        "runtime_ms": 8000,
        "user": "analyst1",
        "timestamp": "2023-03-16T11:30:45",
        "bytes_processed": 120000000
    },
    {
        "query_id": "4",
        "query_text": """
        SELECT 
            t1.*,
            t2.dimension1,
            t2.dimension2
        FROM 
            huge_fact_table t1
        JOIN 
            (SELECT id, dimension1, dimension2 FROM dimension_table WHERE region = 'WEST') t2
        ON 
            t1.dimension_id = t2.id
        WHERE 
            t1.date > '2023-01-01'
        """,
        "runtime_ms": 65000,
        "user": "analyst3",
        "timestamp": "2023-03-17T09:05:18",
        "bytes_processed": 1200000000
    },
    {
        "query_id": "5",
        "query_text": """
        SELECT 
            *
        FROM 
            transactions
        WHERE 
            date = '2023-03-15'
            AND (
                SELECT COUNT(DISTINCT product_id) 
                FROM transaction_items 
                WHERE transaction_id = transactions.id
            ) > 3
        """,
        "runtime_ms": 85000,
        "user": "analyst2",
        "timestamp": "2023-03-17T14:22:33",
        "bytes_processed": 900000000
    }
]

# Initialize LLM Analyzer
try:
    llm_analyzer = LLMQueryAnalyzer(
        model_name=os.environ.get("ANTHROPIC_MODEL", "claude-3-sonnet"),
        api_key=os.environ.get("ANTHROPIC_API_KEY")
    )
    print("LLM Analyzer initialized successfully")
except Exception as e:
    print(f"Warning: Could not initialize LLM analyzer: {e}")
    llm_analyzer = None


# Rule-based analysis fallback functions
class AntiPatterns:
    """Class to identify SQL anti-patterns using rule-based approach"""
    
    @staticmethod
    def select_star(query: str) -> bool:
        """Check if query uses SELECT * without EXCEPT"""
        pattern = r'SELECT\s+\*\s+FROM'
        no_except_pattern = r'SELECT\s+\*\s+EXCEPT\s*\('
        return bool(re.search(pattern, query, re.IGNORECASE)) and not bool(re.search(no_except_pattern, query, re.IGNORECASE))
    
    @staticmethod
    def multiple_with_clauses(query: str) -> bool:
        """Check if query has many WITH clauses that could be optimized"""
        with_count = len(re.findall(r'\bWITH\b', query, re.IGNORECASE))
        return with_count > 3
    
    @staticmethod
    def subquery_with_aggregation(query: str) -> bool:
        """Check for subqueries with aggregation functions"""
        pattern = r'\(\s*SELECT.*?(COUNT|SUM|AVG|MIN|MAX).*?FROM.*?\)'
        return bool(re.search(pattern, query, re.IGNORECASE))
    
    @staticmethod
    def subquery_with_distinct(query: str) -> bool:
        """Check for subqueries with DISTINCT"""
        pattern = r'\(\s*SELECT\s+DISTINCT.*?FROM.*?\)'
        return bool(re.search(pattern, query, re.IGNORECASE))
    
    @staticmethod
    def too_many_joins(query: str) -> bool:
        """Check if query has many joins that could be a performance issue"""
        join_count = len(re.findall(r'\bJOIN\b', query, re.IGNORECASE))
        return join_count > 3
    
    @staticmethod
    def order_by_without_limit(query: str) -> bool:
        """Check for ORDER BY without LIMIT"""
        has_order_by = bool(re.search(r'\bORDER\s+BY\b', query, re.IGNORECASE))
        has_limit = bool(re.search(r'\bLIMIT\b\s+\d+', query, re.IGNORECASE))
        return has_order_by and not has_limit


class RuleBasedQueryOptimizer:
    """Class to optimize SQL queries using rule-based approach (fallback)"""
    
    @staticmethod
    def optimize_select_star(query: str) -> str:
        """Replace SELECT * with specific columns"""
        return query.replace("SELECT *", "SELECT id, name, value, timestamp /* specify only needed columns */")
    
    @staticmethod
    def optimize_with_clauses(query: str) -> str:
        """Suggestion to optimize multiple WITH clauses"""
        return "-- Recommendation: Consider combining related WITH clauses\n" + query
    
    @staticmethod
    def optimize_subquery_with_aggregation(query: str) -> str:
        """Optimize subqueries with aggregation"""
        return "-- Recommendation: Consider using JOIN with pre-aggregated tables instead of subqueries\n" + query
    
    @staticmethod
    def optimize_distinct_in_subquery(query: str) -> str:
        """Optimize DISTINCT in subqueries"""
        return "-- Recommendation: Consider using EXISTS or GROUP BY instead of DISTINCT in subqueries\n" + query
    
    @staticmethod
    def add_limit_to_order_by(query: str) -> str:
        """Add LIMIT to queries with ORDER BY"""
        if "ORDER BY" in query.upper() and "LIMIT" not in query.upper():
            return query + "\nLIMIT 1000 /* Added limit to improve performance */"
        return query


# Define MCP Tools
@mcp.tool()
def get_slow_queries(min_runtime: int = 0, user: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get slow queries from the database with optional filtering
    
    Args:
        min_runtime: Minimum runtime in milliseconds to filter queries
        user: Optional username to filter queries by specific user
        
    Returns:
        List of slow queries matching the criteria
    """
    filtered_queries = []
    
    for query in MOCK_QUERY_DATA:
        if query["runtime_ms"] >= min_runtime:
            if user is None or query["user"] == user:
                filtered_queries.append(query)
    
    return filtered_queries


@mcp.tool()
def get_query_by_id(query_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a specific query by its ID
    
    Args:
        query_id: The ID of the query to retrieve
        
    Returns:
        Query data if found, None otherwise
    """
    for query in MOCK_QUERY_DATA:
        if query["query_id"] == query_id:
            return query
    
    return None


@mcp.tool()
def analyze_query(query_text: str) -> Dict[str, Any]:
    """
    Analyze a SQL query for anti-patterns and performance issues
    
    Args:
        query_text: The SQL query to analyze
        
    Returns:
        Analysis results including detected issues and explanations
    """
    # Try LLM-based analysis if available
    if llm_analyzer:
        try:
            llm_analysis = llm_analyzer.analyze_query(query_text)
            
            # Convert LLM analysis to the expected format
            analysis_result = {
                "query_text": query_text,
                "analysis": llm_analysis["analysis"],
                "explanations": llm_analysis.get("explanations", {}),
                "issues_found": any(llm_analysis["analysis"].values())
            }
            return analysis_result
        except Exception as e:
            print(f"LLM analysis failed: {e}")
    
    # Fallback to rule-based analysis
    anti_patterns = AntiPatterns()
    rule_analysis = {
        "select_star": anti_patterns.select_star(query_text),
        "multiple_with_clauses": anti_patterns.multiple_with_clauses(query_text),
        "subquery_with_aggregation": anti_patterns.subquery_with_aggregation(query_text),
        "subquery_with_distinct": anti_patterns.subquery_with_distinct(query_text),
        "too_many_joins": anti_patterns.too_many_joins(query_text),
        "order_by_without_limit": anti_patterns.order_by_without_limit(query_text)
    }
    
    # Create basic explanations for rule-based analysis
    explanations = {}
    for issue, detected in rule_analysis.items():
        if detected:
            if issue == "select_star":
                explanations[issue] = "Using SELECT * retrieves unnecessary columns, increasing I/O and network load."
            elif issue == "multiple_with_clauses":
                explanations[issue] = "Too many WITH clauses can make query optimization difficult."
            elif issue == "subquery_with_aggregation":
                explanations[issue] = "Subqueries with aggregation can be inefficient - consider pre-aggregation."
            elif issue == "subquery_with_distinct":
                explanations[issue] = "DISTINCT in subqueries can be expensive - consider alternatives."
            elif issue == "too_many_joins":
                explanations[issue] = "Having many joins can lead to performance issues - consider denormalizing."
            elif issue == "order_by_without_limit":
                explanations[issue] = "ORDER BY without LIMIT sorts the entire result set, which is costly."
    
    return {
        "query_text": query_text,
        "analysis": rule_analysis,
        "explanations": explanations,
        "issues_found": any(rule_analysis.values())
    }


@mcp.tool()
def optimize_query(query_text: str, analysis: Dict[str, Any]) -> str:
    """
    Generate an optimized version of a SQL query based on analysis
    
    Args:
        query_text: The original SQL query to optimize
        analysis: Analysis results from analyze_query
        
    Returns:
        Optimized SQL query with explanatory comments
    """
    # Try LLM-based optimization if available
    if llm_analyzer:
        try:
            optimized_query = llm_analyzer.optimize_query(query_text, analysis)
            return optimized_query
        except Exception as e:
            print(f"LLM optimization failed: {e}")
    
    # Fallback to rule-based optimization
    optimizer = RuleBasedQueryOptimizer()
    optimized_query = query_text
    
    # Apply optimizations based on identified issues
    if analysis["analysis"].get("select_star", False):
        optimized_query = optimizer.optimize_select_star(optimized_query)
    
    if analysis["analysis"].get("multiple_with_clauses", False):
        optimized_query = optimizer.optimize_with_clauses(optimized_query)
    
    if analysis["analysis"].get("subquery_with_aggregation", False):
        optimized_query = optimizer.optimize_subquery_with_aggregation(optimized_query)
    
    if analysis["analysis"].get("subquery_with_distinct", False):
        optimized_query = optimizer.optimize_distinct_in_subquery(optimized_query)
    
    if analysis["analysis"].get("order_by_without_limit", False):
        optimized_query = optimizer.add_limit_to_order_by(optimized_query)
    
    return optimized_query


# FastAPI route handlers
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Render the main page"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/slow-queries", response_class=HTMLResponse)
async def get_slow_queries_page(request: Request):
    """Render the slow queries page"""
    min_runtime = request.query_params.get("min_runtime", "0")
    user = request.query_params.get("user", "")
    
    # Parse min_runtime to int with error handling
    try:
        min_runtime_int = int(min_runtime)
    except ValueError:
        min_runtime_int = 0
    
    # Use the MCP tool
    queries = get_slow_queries(min_runtime_int, user if user else None)
    
    # Render the template with results
    return templates.TemplateResponse(
        "slow_queries.html", 
        {
            "request": request, 
            "queries": queries,
            "min_runtime": min_runtime,
            "user": user
        }
    )


@app.get("/analyze", response_class=HTMLResponse)
async def analyze_page(request: Request, query_id: Optional[str] = None):
    """Render the analysis page"""
    if query_id:
        # Get query by ID using the MCP tool
        query = get_query_by_id(query_id)
        
        if query:
            # Analyze the query using the MCP tool
            analysis = analyze_query(query["query_text"])
            
            # Store analysis in session for optimization step
            request.session["last_query"] = query["query_text"]
            request.session["last_analysis"] = analysis
            
            return templates.TemplateResponse(
                "analyze.html", 
                {
                    "request": request, 
                    "analysis": analysis,
                    "query_id": query_id,
                    "query_text": query["query_text"]
                }
            )
    
    return templates.TemplateResponse("analyze.html", {"request": request})


@app.post("/analyze", response_class=HTMLResponse)
async def analyze_query_endpoint(request: Request, query_text: str = Form(...)):
    """Analyze a query from form submission"""
    # Analyze the query using the MCP tool
    analysis = analyze_query(query_text)
    
    # Store analysis in session for optimization step
    request.session["last_query"] = query_text
    request.session["last_analysis"] = analysis
    
    return templates.TemplateResponse(
        "analyze.html", 
        {
            "request": request,
            "analysis": analysis,
            "query_text": query_text
        }
    )


@app.get("/optimize", response_class=HTMLResponse)
async def optimize_page(request: Request, query_id: Optional[str] = None):
    """Render the optimization page"""
    if query_id:
        # Get query by ID using the MCP tool
        query = get_query_by_id(query_id)
        
        if query:
            # Analyze the query using the MCP tool
            analysis = analyze_query(query["query_text"])
            
            # Optimize the query using the MCP tool
            optimized_query = optimize_query(query["query_text"], analysis)
            
            optimization = {
                "original_query": query["query_text"],
                "analysis": analysis["analysis"],
                "explanations": analysis.get("explanations", {}),
                "optimized_query": optimized_query
            }
            
            return templates.TemplateResponse(
                "optimize.html", 
                {
                    "request": request, 
                    "optimization": optimization,
                    "query_id": query_id
                }
            )
    
    # Check if we have a stored query and analysis from the previous step
    last_query = request.session.get("last_query")
    last_analysis = request.session.get("last_analysis")
    
    if last_query and last_analysis:
        # Optimize the stored query
        optimized_query = optimize_query(last_query, last_analysis)
        
        optimization = {
            "original_query": last_query,
            "analysis": last_analysis["analysis"],
            "explanations": last_analysis.get("explanations", {}),
            "optimized_query": optimized_query
        }
        
        # Clear the session data
        if "last_query" in request.session:
            del request.session["last_query"]
        if "last_analysis" in request.session:
            del request.session["last_analysis"]
        
        return templates.TemplateResponse(
            "optimize.html", 
            {
                "request": request, 
                "optimization": optimization
            }
        )
    
    return templates.TemplateResponse("optimize.html", {"request": request})


@app.post("/optimize", response_class=HTMLResponse)
async def optimize_query_endpoint(request: Request, query_text: str = Form(...)):
    """Optimize a query from form submission"""
    # Analyze the query using the MCP tool
    analysis = analyze_query(query_text)
    
    # Optimize the query using the MCP tool
    optimized_query = optimize_query(query_text, analysis)
    
    optimization = {
        "original_query": query_text,
        "analysis": analysis["analysis"],
        "explanations": analysis.get("explanations", {}),
        "optimized_query": optimized_query
    }
    
    return templates.TemplateResponse(
        "optimize.html", 
        {
            "request": request, 
            "optimization": optimization,
            "query_text": query_text
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)