import json
import os
from typing import Dict, Any

import requests



class LLMQueryAnalyzer:
    """Class to analyze SQL queries using LLMs"""
    
    def __init__(self, model_name="claude-3-5-sonnet-20240620", api_key=None):
        """Initialize the LLM Query Analyzer
        
        Args:
            model_name: The name of the LLM model to use
            api_key: API key for the LLM service
        """
        self.model_name = model_name
        # Try to get API key from environment if not provided
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        
        if not self.api_key:
            raise ValueError("API key is required. Set ANTHROPIC_API_KEY environment variable or pass it directly.")
    
    def analyze_query(self, query_text: str) -> Dict[str, Any]:
        """Analyze a SQL query for anti-patterns using Claude
        
        Args:
            query_text: The SQL query to analyze
            
        Returns:
            Dict containing analysis results
        """
        system_prompt = """
        You are an expert BigQuery SQL analyzer. Your task is to analyze SQL queries for anti-patterns 
        and performance issues. Focus on the following common issues:
        
        1. Using SELECT * without EXCEPT - Retrieving unnecessary columns
        2. Multiple WITH clauses that could be optimized
        3. Subqueries with aggregation functions
        4. Subqueries with DISTINCT
        5. Too many JOINs
        6. ORDER BY without LIMIT
        
        For each issue, indicate if it's present in the query and provide a brief explanation why it's problematic.
        
        Return your analysis as a JSON object with the following structure:
        {
            "analysis": {
                "select_star": true/false,
                "multiple_with_clauses": true/false,
                "subquery_with_aggregation": true/false,
                "subquery_with_distinct": true/false,
                "too_many_joins": true/false,
                "order_by_without_limit": true/false
            },
            "explanations": {
                "select_star": "Explanation if issue is detected...",
                ...
            }
        }
        """
        
        user_prompt = f"Analyze the following BigQuery SQL query for performance issues and anti-patterns:\n\n```sql\n{query_text}\n```"
        
        try:
            headers = {
                "x-api-key": self.api_key,
                "content-type": "application/json",
                "anthropic-version": "2023-06-01"
            }
            
            # Updated API request format
            data = {
                "model": self.model_name,
                "system": system_prompt,  # System prompt as separate parameter, not a message
                "messages": [
                    {"role": "user", "content": user_prompt}
                ],
                "max_tokens": 1000,
                "temperature": 0
            }
            
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=data
            )
            
            if response.status_code != 200:
                raise Exception(f"API request failed with status code {response.status_code}: {response.text}")
            
            response_data = response.json()
            content = response_data["content"][0]["text"]
            
            # Extract JSON from content
            try:
                # Try to parse the entire content as JSON
                result = json.loads(content)
            except json.JSONDecodeError:
                # If the entire content isn't valid JSON, try to extract JSON parts
                import re
                json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(1))
                else:
                    # Last resort, search for anything that looks like JSON
                    json_match = re.search(r'{.*}', content, re.DOTALL)
                    if json_match:
                        result = json.loads(json_match.group(0))
                    else:
                        raise Exception("Could not extract JSON from LLM response")
            
            # Ensure the result has the expected structure
            if "analysis" not in result:
                raise Exception("LLM response doesn't contain 'analysis' key")
            
            return result
            
        except Exception as e:
            # Fallback to basic analysis in case of API issues
            print(f"Error using LLM for query analysis: {e}")
            return {
                "analysis": {
                    "select_star": "*" in query_text.upper(),
                    "multiple_with_clauses": query_text.upper().count("WITH") > 3,
                    "subquery_with_aggregation": any(func in query_text.upper() for func in ["COUNT(", "SUM(", "AVG(", "MIN(", "MAX("]),
                    "subquery_with_distinct": "DISTINCT" in query_text.upper(),
                    "too_many_joins": query_text.upper().count("JOIN") > 3,
                    "order_by_without_limit": "ORDER BY" in query_text.upper() and "LIMIT" not in query_text.upper()
                },
                "explanations": {
                    "select_star": "Using SELECT * retrieves unnecessary columns." if "*" in query_text.upper() else "",
                    "multiple_with_clauses": "Too many WITH clauses found." if query_text.upper().count("WITH") > 3 else "",
                    "subquery_with_aggregation": "Subqueries with aggregation can be inefficient." if any(func in query_text.upper() for func in ["COUNT(", "SUM(", "AVG(", "MIN(", "MAX("]) else "",
                    "subquery_with_distinct": "DISTINCT in subqueries can be expensive." if "DISTINCT" in query_text.upper() else "",
                    "too_many_joins": "Having many joins can lead to performance issues." if query_text.upper().count("JOIN") > 3 else "",
                    "order_by_without_limit": "ORDER BY without LIMIT sorts the entire result set." if "ORDER BY" in query_text.upper() and "LIMIT" not in query_text.upper() else ""
                }
            }
    
    def optimize_query(self, query_text: str, analysis: Dict[str, Any]) -> str:
        """Generate an optimized version of the query based on the analysis
        
        Args:
            query_text: The original SQL query
            analysis: Analysis results from analyze_query method
            
        Returns:
            Optimized SQL query
        """
        system_prompt = """
        You are an expert BigQuery SQL optimizer. Your task is to optimize a SQL query based on 
        detected anti-patterns. The analysis has identified specific issues, and you should address 
        each one in your optimization.
        
        When optimizing the query:
        1. If SELECT * is used, replace it with specific columns that would likely be needed
        2. If there are multiple WITH clauses, suggest consolidation or optimization
        3. If there are subqueries with aggregation, suggest pre-aggregation approaches
        4. If DISTINCT is used in subqueries, suggest alternatives
        5. If there are too many JOINs, suggest denormalization or materialized views
        6. If ORDER BY is used without LIMIT, add an appropriate LIMIT
        
        Provide the optimized query as well as explanatory comments for each change.
        
        Your output should be formatted as a complete SQL query with comments explaining the optimizations.
        """
        
        # Convert analysis to string format for the prompt
        analysis_str = json.dumps(analysis, indent=2)
        
        user_prompt = f"""
        Original query:
        ```sql
        {query_text}
        ```
        
        Analysis results:
        ```json
        {analysis_str}
        ```
        
        Please provide an optimized version of this query that addresses the identified issues.
        Include explanatory comments about your changes.
        """
        
        try:
            headers = {
                "x-api-key": self.api_key,
                "content-type": "application/json",
                "anthropic-version": "2023-06-01"
            }
            
            # Updated API request format
            data = {
                "model": self.model_name,
                "system": system_prompt,  # System prompt as separate parameter, not a message
                "messages": [
                    {"role": "user", "content": user_prompt}
                ],
                "max_tokens": 2000,
                "temperature": 0
            }
            
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=data
            )
            
            if response.status_code != 200:
                raise Exception(f"API request failed with status code {response.status_code}: {response.text}")
            
            response_data = response.json()
            optimized_query = response_data["content"][0]["text"]
            
            # Extract SQL from content if it's wrapped in code blocks
            import re
            sql_match = re.search(r'```sql\s*(.*?)\s*```', optimized_query, re.DOTALL)
            if sql_match:
                optimized_query = sql_match.group(1)
            
            return optimized_query
            
        except Exception as e:
            # Fallback to basic optimization in case of API issues
            print(f"Error using LLM for query optimization: {e}")
            
            optimized_query = query_text
            
            # Apply basic optimizations based on analysis
            if analysis["analysis"].get("select_star", False):
                optimized_query = optimized_query.replace("SELECT *", "SELECT id, name, value, timestamp /* Select only necessary columns */")
            
            if analysis["analysis"].get("order_by_without_limit", False) and "LIMIT" not in optimized_query:
                optimized_query += "\nLIMIT 1000 /* Added limit to improve performance */"
            
            return optimized_query
