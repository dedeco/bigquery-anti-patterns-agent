from typing import Dict, List, Any, Optional
from fastapi import FastAPI, Request, Form, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import os
from mcp_module.server import FastMCP
from llm.analyzer import LLMQueryAnalyzer
from starlette.middleware.sessions import SessionMiddleware
from data.mock_data import MOCK_QUERY_DATA
from analizer.anti_patterns import AntiPatterns
from analizer.query_optimizer import RuleBasedQueryOptimizer

# Set up FastMCP
mcp = FastMCP("BigQuery Query Analyzer")
app = FastAPI(title="BigQuery Query Analyzer")
app.add_middleware(SessionMiddleware, secret_key="your-secret-key")
templates = Jinja2Templates(directory="templates")

# Initialize LLM Analyzer
try:
    llm_analyzer = LLMQueryAnalyzer(
        model_name=os.environ.get("ANTHROPIC_MODEL", "claude-3-sonnet-20240229"),
        api_key=os.environ.get("ANTHROPIC_API_KEY")
    )
    print("LLM Analyzer initialized successfully")
except Exception as e:
    print(f"Warning: Could not initialize LLM analyzer: {e}")
    llm_analyzer = None

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
    # Debug print
    print(f"\n=== Starting Query Optimization ===")
    print(f"Input query: {query_text}")
    
    # Analyze the query using the MCP tool
    analysis = analyze_query(query_text)
    print(f"Analysis result: {analysis}")
    
    # Optimize the query using the MCP tool
    optimized_query = optimize_query(query_text, analysis)
    print(f"Optimized query: {optimized_query}")
    
    optimization = {
        "original_query": query_text,
        "analysis": analysis["analysis"],
        "explanations": analysis.get("explanations", {}),
        "optimized_query": optimized_query
    }
    
    # Debug print the final data structure
    print(f"Final optimization data: {optimization}")
    print("=== End Query Optimization ===\n")
    
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