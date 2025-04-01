"""Module for identifying SQL anti-patterns"""
import re

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