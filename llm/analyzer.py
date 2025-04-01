"""LLM-based query analyzer"""
import json
import os
import re
from typing import Dict, Any
import requests
import time
import random

class LLMQueryAnalyzer:
    """Class to analyze SQL queries using LLMs"""

    def __init__(self, model_name="claude-3-sonnet-20240229", api_key=None, max_retries=3, initial_delay=1):
        """Initialize the LLM Query Analyzer
        
        Args:
            model_name: The name of the LLM model to use
            api_key: API key for the LLM service
            max_retries: Maximum number of retry attempts for API calls
            initial_delay: Initial delay in seconds between retries
        """
        self.model_name = model_name
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.max_retries = max_retries
        self.initial_delay = initial_delay

        if not self.api_key:
            raise ValueError(
                "API key is required. Set ANTHROPIC_API_KEY environment variable or pass it directly.")

    def _make_api_request(self, headers: Dict, data: Dict) -> Dict:
        """Make API request with retry logic"""
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=data,
                    timeout=30  # Add timeout
                )

                if response.status_code == 200:
                    return response.json()
                
                # If we get a 529 (overloaded), retry with exponential backoff
                if response.status_code == 529:
                    if attempt < self.max_retries - 1:  # Don't sleep on last attempt
                        delay = self.initial_delay * (2 ** attempt) + random.uniform(0, 1)
                        print(f"API overloaded. Retrying in {delay:.2f} seconds...")
                        time.sleep(delay)
                        continue
                
                # For other errors, raise exception
                response.raise_for_status()
                
            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries - 1:
                    delay = self.initial_delay * (2 ** attempt) + random.uniform(0, 1)
                    print(f"Request failed. Retrying in {delay:.2f} seconds... Error: {str(e)}")
                    time.sleep(delay)
                    continue
                raise

        raise Exception(f"API request failed after {self.max_retries} attempts")

    def analyze_query(self, query_text: str) -> Dict[str, Any]:
        """Analyze a SQL query for anti-patterns using Claude"""
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

            data = {
                "model": self.model_name,
                "system": system_prompt,
                "messages": [
                    {"role": "user", "content": user_prompt}
                ],
                "max_tokens": 1000,
                "temperature": 0
            }

            print("request data: ", data)

            response_data = self._make_api_request(headers, data)

            if not response_data.get("content"):
                raise Exception("No content in LLM response")
                
            content = response_data["content"][0]["text"]

            # Extract JSON from content
            try:
                # Try to parse the entire content as JSON
                result = json.loads(content)
            except json.JSONDecodeError:
                # If the entire content isn't valid JSON, try to extract JSON parts
                json_match = re.search(r'```json\s*(.*?)\s*```', content,
                                     re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(1))
                else:
                    # Last resort, search for anything that looks like JSON
                    json_match = re.search(r'{.*}', content, re.DOTALL)
                    if json_match:
                        result = json.loads(json_match.group(0))
                    else:
                        raise Exception(
                            "Could not extract JSON from LLM response")


            print("result: ", result) 

            # Ensure the result has the expected structure
            if "analysis" not in result:
                raise Exception("LLM response doesn't contain 'analysis' key")

            return result

        except Exception as e:
            print(f"Error in LLM analysis: {str(e)}")
            # Return a structured fallback response instead of None
            return {
                "analysis": {
                    "select_star": "*" in query_text.upper(),
                    "multiple_with_clauses": query_text.upper().count("WITH") > 3,
                    "subquery_with_aggregation": any(
                        func in query_text.upper() for func in
                        ["COUNT(", "SUM(", "AVG(", "MIN(", "MAX("]),
                    "subquery_with_distinct": "DISTINCT" in query_text.upper(),
                    "too_many_joins": query_text.upper().count("JOIN") > 3,
                    "order_by_without_limit": "ORDER BY" in query_text.upper() and "LIMIT" not in query_text.upper()
                },
                "explanations": {
                    "select_star": "Using SELECT * retrieves unnecessary columns." if "*" in query_text.upper() else "",
                    "multiple_with_clauses": "Too many WITH clauses found." if query_text.upper().count("WITH") > 3 else "",
                    "subquery_with_aggregation": "Subqueries with aggregation can be inefficient." if any(
                        func in query_text.upper() for func in ["COUNT(", "SUM(", "AVG(", "MIN(", "MAX("]) else "",
                    "subquery_with_distinct": "DISTINCT in subqueries can be expensive." if "DISTINCT" in query_text.upper() else "",
                    "too_many_joins": "Having many joins can lead to performance issues." if query_text.upper().count("JOIN") > 3 else "",
                    "order_by_without_limit": "ORDER BY without LIMIT sorts the entire result set." if "ORDER BY" in query_text.upper() and "LIMIT" not in query_text.upper() else ""
                }
            }

    def optimize_query(self, query_text: str, analysis: Dict[str, Any]) -> str:
        """Generate an optimized version of the query based on the analysis"""
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
        
        Return the optimized query with explanatory comments.
        """

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
        
        Please provide an optimized version of this query addressing the identified issues.
        """

        try:
            headers = {
                "x-api-key": self.api_key,
                "content-type": "application/json",
                "anthropic-version": "2023-06-01"
            }

            data = {
                "model": self.model_name,
                "system": system_prompt,
                "messages": [
                    {"role": "user", "content": user_prompt}
                ],
                "max_tokens": 1000,
                "temperature": 0
            }

            response_data = self._make_api_request(headers, data)
            
            if not response_data.get("content"):
                print("No content in response data")
                raise Exception("No content in LLM response")
                
            content = response_data["content"][0]["text"]
            print("Received response:", content[:200] + "...")  # Log first 200 chars

            # Extract the SQL from the response
            sql_match = re.search(r'```sql\s*(.*?)\s*```', content, re.DOTALL)
            if sql_match:
                optimized_sql = sql_match.group(1).strip()
                print("Extracted optimized SQL")
                return optimized_sql
            
            print("No SQL block found, returning full content")
            return content.strip()

        except Exception as e:
            print(f"Error in LLM optimization: {str(e)}")
            # Return original query with explanation comment
            return f"""-- Optimization failed due to API overload. Using original query.
-- Please try again in a few moments.
{query_text}""" 