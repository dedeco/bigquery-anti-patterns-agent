import json
import os
import re
from typing import List, Dict, Any, Optional, Union

# Import our LLM analyzer
from llm_integration import LLMQueryAnalyzer
from mcp_module.types import MCPServer, MCPContext, MCPResponse, MCPStreamingResponse, MCPModel

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


class LLMBasedQueryAnalysisConfig:
    """Configuration for LLM-based query analysis"""

    def __init__(self,
                 model_name="claude-3-sonnet",
                 api_key=None,
                 fallback_to_rule_based=True):
        self.model_name = model_name
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.fallback_to_rule_based = fallback_to_rule_based


class AntiPatterns:
    """Class to identify SQL anti-patterns using rule-based approach"""

    @staticmethod
    def select_star(query: str) -> bool:
        """Check if query uses SELECT * without EXCEPT"""
        pattern = r'SELECT\s+\*\s+FROM'
        no_except_pattern = r'SELECT\s+\*\s+EXCEPT\s*\('
        return bool(re.search(pattern, query, re.IGNORECASE)) and not bool(
            re.search(no_except_pattern, query, re.IGNORECASE))

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


class BigQueryAnalysisModel(MCPModel):
    """MCP Model for BigQuery query analysis"""

    def __init__(self, llm_config=None):
        """Initialize with optional LLM configuration"""
        self.anti_patterns = AntiPatterns()
        self.rule_optimizer = RuleBasedQueryOptimizer()

        # Set up LLM analyzer if configuration is provided
        self.llm_config = llm_config or LLMBasedQueryAnalysisConfig()
        try:
            self.llm_analyzer = LLMQueryAnalyzer(
                model_name=self.llm_config.model_name,
                api_key=self.llm_config.api_key
            )
        except Exception as e:
            print(f"Warning: Could not initialize LLM analyzer: {e}")
            self.llm_analyzer = None

    def get_slow_queries(self, min_runtime: int = 0, user: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get slow queries with optional filtering"""
        filtered_queries = []

        for query in MOCK_QUERY_DATA:
            if query["runtime_ms"] >= min_runtime:
                if user is None or query["user"] == user:
                    filtered_queries.append(query)

        return filtered_queries

    def analyze_query(self, query_text: str) -> Dict[str, Any]:
        """Analyze a query for anti-patterns using LLM if available, falling back to rules"""
        if self.llm_analyzer:
            try:
                llm_analysis = self.llm_analyzer.analyze_query(query_text)

                # Convert LLM analysis to the expected format
                analysis_result = {
                    "analysis": llm_analysis["analysis"],
                    "explanations": llm_analysis.get("explanations", {}),
                    "issues_found": any(llm_analysis["analysis"].values())
                }
                return analysis_result
            except Exception as e:
                print(f"LLM analysis failed: {e}")
                if not self.llm_config.fallback_to_rule_based:
                    raise

        # Fallback to rule-based analysis if LLM fails or isn't available
        rule_analysis = {
            "select_star": self.anti_patterns.select_star(query_text),
            "multiple_with_clauses": self.anti_patterns.multiple_with_clauses(query_text),
            "subquery_with_aggregation": self.anti_patterns.subquery_with_aggregation(query_text),
            "subquery_with_distinct": self.anti_patterns.subquery_with_distinct(query_text),
            "too_many_joins": self.anti_patterns.too_many_joins(query_text),
            "order_by_without_limit": self.anti_patterns.order_by_without_limit(query_text)
        }

        # Create basic explanations for rule-based analysis
        explanations = {}
        for issue, detected in rule_analysis.items():
            if detected:
                if issue == "select_star":
                    explanations[
                        issue] = "Using SELECT * retrieves unnecessary columns, increasing I/O and network load."
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
            "analysis": rule_analysis,
            "explanations": explanations,
            "issues_found": any(rule_analysis.values())
        }

    def optimize_query(self, query_text: str, analysis: Dict[str, Any]) -> str:
        """Generate optimized query based on identified issues"""
        if self.llm_analyzer:
            try:
                # Use LLM to optimize the query based on analysis
                optimized_query = self.llm_analyzer.optimize_query(query_text, analysis)
                return optimized_query
            except Exception as e:
                print(f"LLM optimization failed: {e}")
                if not self.llm_config.fallback_to_rule_based:
                    raise

        # Fallback to rule-based optimization
        optimized_query = query_text

        # Apply optimizations based on identified issues
        if analysis["analysis"].get("select_star", False):
            optimized_query = self.rule_optimizer.optimize_select_star(optimized_query)

        if analysis["analysis"].get("multiple_with_clauses", False):
            optimized_query = self.rule_optimizer.optimize_with_clauses(optimized_query)

        if analysis["analysis"].get("subquery_with_aggregation", False):
            optimized_query = self.rule_optimizer.optimize_subquery_with_aggregation(optimized_query)

        if analysis["analysis"].get("subquery_with_distinct", False):
            optimized_query = self.rule_optimizer.optimize_distinct_in_subquery(optimized_query)

        if analysis["analysis"].get("order_by_without_limit", False):
            optimized_query = self.rule_optimizer.add_limit_to_order_by(optimized_query)

        return optimized_query


# MCP Server implementation
class BigQueryAnalysisServer(MCPServer):
    """MCP Server for BigQuery query analysis"""

    def __init__(self, llm_config=None):
        """Initialize with optional LLM configuration"""
        self.model = BigQueryAnalysisModel(llm_config)

    async def process(self, context: MCPContext) -> Union[MCPResponse, MCPStreamingResponse]:
        """Process incoming MCP context"""
        # Extract action from the context
        action = context.actions[0] if context.actions else None

        if not action:
            return MCPResponse(content="Please specify an action.")

        if action.name == "get_slow_queries":
            # Get parameters with defaults
            min_runtime = action.parameters.get("min_runtime", 0)
            user = action.parameters.get("user", None)

            # Get slow queries
            slow_queries = self.model.get_slow_queries(min_runtime, user)
            return MCPResponse(content=json.dumps(slow_queries, indent=2))

        elif action.name == "analyze_query":
            query_id = action.parameters.get("query_id")
            query_text = action.parameters.get("query_text")

            # If query_id is provided, get the query text from the database
            if query_id and not query_text:
                for query in MOCK_QUERY_DATA:
                    if query["query_id"] == query_id:
                        query_text = query["query_text"]
                        break

            if not query_text:
                return MCPResponse(content="Please provide either query_id or query_text.")

            # Analyze the query
            analysis = self.model.analyze_query(query_text)
            result = {
                "query_text": query_text,
                "analysis": analysis["analysis"],
                "explanations": analysis.get("explanations", {}),
                "issues_found": analysis["issues_found"]
            }
            return MCPResponse(content=json.dumps(result, indent=2))

        elif action.name == "optimize_query":
            query_id = action.parameters.get("query_id")
            query_text = action.parameters.get("query_text")

            # If query_id is provided, get the query text from the database
            if query_id and not query_text:
                for query in MOCK_QUERY_DATA:
                    if query["query_id"] == query_id:
                        query_text = query["query_text"]
                        break

            if not query_text:
                return MCPResponse(content="Please provide either query_id or query_text.")

            # Analyze and optimize the query
            analysis = self.model.analyze_query(query_text)
            optimized_query = self.model.optimize_query(query_text, analysis)

            result = {
                "original_query": query_text,
                "analysis": analysis["analysis"],
                "explanations": analysis.get("explanations", {}),
                "optimized_query": optimized_query
            }
            return MCPResponse(content=json.dumps(result, indent=2))

        else:
            return MCPResponse(content=f"Unknown action: {action.name}")
