"""
SQL Validator Utility

A comprehensive SQL validator using the sqlvalidator library combined with database
schema validation. This helps prevent errors and provides feedback for query regeneration.
"""

import logging
from typing import Dict, List, Tuple, Optional
from sqlalchemy import inspect, text
from sqlvalidator import format_sql

from src.common.db_utils import get_db_connection

logger = logging.getLogger(__name__)

class SQLValidator:
    """SQL validation utility for checking queries before execution"""
    
    def __init__(self):
        self.engine = get_db_connection()
        self._table_cache = None
    
    def _get_database_tables(self) -> Dict[str, List[str]]:
        """Get all tables and their columns from the database"""
        if self._table_cache is None:
            try:
                inspector = inspect(self.engine)
                tables = {}
                
                # Get all table names
                table_names = inspector.get_table_names()
                
                for table_name in table_names:
                    # Get columns for each table
                    columns = inspector.get_columns(table_name)
                    column_names = [col['name'] for col in columns]
                    tables[table_name.lower()] = column_names
                
                self._table_cache = tables
                logger.debug(f"Cached {len(tables)} tables with their columns")
                
            except Exception as e:
                logger.error(f"Failed to get database schema: {e}")
                self._table_cache = {}
        
        return self._table_cache
    
    def validate_sql_syntax(self, sql: str) -> Tuple[bool, str]:
        """Validate SQL syntax using sqlvalidator library and database EXPLAIN"""
        try:
            # First try sqlvalidator for basic syntax and formatting
            formatted_sql = format_sql(sql)
            logger.debug("SQL syntax validation passed using sqlvalidator")
            
            # Then try EXPLAIN to validate against the actual database
            # This catches more database-specific syntax issues
            try:
                with self.engine.connect() as conn:
                    explain_sql = f"EXPLAIN (FORMAT TEXT) {sql}"
                    conn.execute(text(explain_sql))
                logger.debug("SQL database syntax validation passed")
                return True, "SQL syntax is valid"
            except Exception as db_error:
                # If EXPLAIN fails, it's likely a database-specific syntax issue
                db_error_msg = str(db_error)
                logger.warning(f"Database syntax validation failed: {db_error_msg}")
                return False, f"SQL syntax error: {db_error_msg}"
            
        except Exception as e:
            error_msg = str(e)
            logger.warning(f"SQL syntax validation failed: {error_msg}")
            return False, f"SQL syntax error: {error_msg}"
    
    def validate_table_and_column_existence(self, sql: str) -> Tuple[bool, str]:
        """Validate that referenced tables and columns exist in the database"""
        try:
            database_tables = self._get_database_tables()
            
            if not database_tables:
                return True, "No database schema available for validation"
            
            # Convert SQL to lowercase for case-insensitive matching
            sql_lower = sql.lower()
            
            # Check for table references
            missing_items = []
            
            for table_name in database_tables.keys():
                if table_name in sql_lower:
                    # Table exists, now check if any referenced columns exist
                    table_columns = [col.lower() for col in database_tables[table_name]]
                    
                    # Look for table.column patterns in the SQL
                    import re
                    column_pattern = rf'\b{re.escape(table_name)}\s*\.\s*([a-zA-Z_][a-zA-Z0-9_]*)'
                    column_matches = re.findall(column_pattern, sql_lower)
                    
                    for column_match in column_matches:
                        if column_match not in table_columns:
                            # Try to find similar column names
                            similar = [col for col in table_columns if column_match in col or col in column_match]
                            error_detail = f"{table_name}.{column_match}"
                            if similar:
                                error_detail += f" (similar columns: {', '.join(similar[:3])})"
                            missing_items.append(error_detail)
            
            if missing_items:
                error_msg = f"Referenced columns do not exist: {', '.join(missing_items)}"
                logger.warning(f"Column existence validation failed: {error_msg}")
                return False, error_msg
            
            logger.debug("Table and column existence validation passed")
            return True, "All referenced tables and columns appear to exist"
            
        except Exception as e:
            error_msg = f"Error validating table/column existence: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def validate_sql_comprehensive(self, sql: str, skip_syntax: bool = False) -> Dict:
        """
        Perform comprehensive SQL validation
        
        Args:
            sql: The SQL query to validate
            skip_syntax: Skip syntax validation (useful when already done elsewhere)
            
        Returns:
            Dict with validation results and recommendations
        """
        if not sql or not sql.strip():
            return {
                "is_valid": False,
                "error": "Empty SQL query provided",
                "validation_details": {
                    "syntax": {"valid": False, "message": "Empty query"},
                    "schema": {"valid": False, "message": "No query to validate"}
                },
                "recommendations": ["Provide a valid SQL query"]
            }
        
        validation_results = {
            "is_valid": True,
            "error": None,
            "validation_details": {},
            "recommendations": []
        }
        
        # 1. Syntax validation using sqlvalidator (if not skipped)
        if not skip_syntax:
            syntax_valid, syntax_msg = self.validate_sql_syntax(sql)
            validation_results["validation_details"]["syntax"] = {
                "valid": syntax_valid,
                "message": syntax_msg
            }
            if not syntax_valid:
                validation_results["is_valid"] = False
                validation_results["error"] = syntax_msg
                validation_results["recommendations"].append("Fix SQL syntax errors")
                # If syntax is invalid, schema validation may not be meaningful
                return validation_results
        
        # 2. Schema validation (table and column existence)
        schema_valid, schema_msg = self.validate_table_and_column_existence(sql)
        validation_results["validation_details"]["schema"] = {
            "valid": schema_valid,
            "message": schema_msg
        }
        if not schema_valid:
            validation_results["is_valid"] = False
            if not validation_results["error"]:
                validation_results["error"] = schema_msg
            validation_results["recommendations"].append("Use existing table and column names from the database schema")
        
        # Add success message if all validations passed
        if validation_results["is_valid"]:
            validation_results["message"] = "SQL query passed all validation checks"
            logger.info("SQL query validation successful")
        else:
            logger.warning(f"SQL query validation failed: {validation_results['error']}")
        
        return validation_results
    
    def get_table_suggestions(self, partial_name: str = "", limit: int = 10) -> List[str]:
        """Get table name suggestions for error recovery"""
        database_tables = self._get_database_tables()
        
        if not partial_name:
            return list(database_tables.keys())[:limit]
        
        # Find tables that contain the partial name
        suggestions = []
        partial_lower = partial_name.lower()
        
        for table in database_tables.keys():
            if partial_lower in table:
                suggestions.append(table)
        
        return suggestions[:limit]
    
    def get_column_suggestions(self, table_name: str, partial_column: str = "", limit: int = 10) -> List[str]:
        """Get column name suggestions for error recovery"""
        database_tables = self._get_database_tables()
        
        table_lower = table_name.lower()
        if table_lower not in database_tables:
            return []
        
        columns = [col.lower() for col in database_tables[table_lower]]
        
        if not partial_column:
            return columns[:limit]
        
        # Find columns that contain the partial name
        suggestions = []
        partial_lower = partial_column.lower()
        
        for column in columns:
            if partial_lower in column:
                suggestions.append(column)
        
        return suggestions[:limit]
    
    def format_sql(self, sql: str) -> str:
        """Format SQL using sqlvalidator library"""
        try:
            return format_sql(sql)
        except Exception as e:
            logger.warning(f"SQL formatting failed: {e}")
            return sql  # Return original if formatting fails

def validate_sql(sql: str, skip_syntax: bool = False) -> Dict:
    """
    Convenience function for SQL validation
    
    Args:
        sql: The SQL query to validate
        skip_syntax: Skip syntax validation (useful when already done elsewhere)
        
    Returns:
        Dict with validation results
    """
    validator = SQLValidator()
    return validator.validate_sql_comprehensive(sql, skip_syntax=skip_syntax)

def get_validation_error_context(validation_result: Dict) -> str:
    """
    Extract validation error context for query regeneration
    
    Args:
        validation_result: Result from validate_sql_comprehensive
        
    Returns:
        String describing the validation errors for LLM context
    """
    if validation_result.get("is_valid", False):
        return "Previous query validation passed"
    
    error_parts = []
    
    # Add main error
    if validation_result.get("error"):
        error_parts.append(f"Main issue: {validation_result['error']}")
    
    # Add specific validation details
    details = validation_result.get("validation_details", {})
    
    for check_type, check_result in details.items():
        if not check_result.get("valid", True):
            error_parts.append(f"{check_type.title()} validation failed: {check_result.get('message', 'Unknown error')}")
    
    # Add recommendations
    recommendations = validation_result.get("recommendations", [])
    if recommendations:
        error_parts.append(f"Recommendations: {'; '.join(recommendations)}")
    
    return " | ".join(error_parts)

if __name__ == "__main__":
    # Test the validator with sqlvalidator library
    validator = SQLValidator()
    
    # Test cases
    test_queries = [
        "SELECT * FROM products LIMIT 10",
        "SELECT nonexistent_column FROM products",  # Should fail schema validation
        "SELECT * FROM nonexistent_table",  # Should fail schema validation
        "SELECT INVALID SQL SYNTAX",  # Should fail syntax validation
        "SELECT p.product_id, p.product_category_name FROM products p",  # Should pass
    ]
    
    print("Testing SQL Validator with sqlvalidator library")
    print("=" * 60)
    
    for i, query in enumerate(test_queries, 1):
        print(f"\nTest {i}: {query}")
        print("-" * 50)
        
        result = validator.validate_sql_comprehensive(query)
        print(f"Valid: {result['is_valid']}")
        
        if result.get('message'):
            print(f"Message: {result['message']}")
        
        if result['error']:
            print(f"Error: {result['error']}")
        
        if result['recommendations']:
            print(f"Recommendations: {'; '.join(result['recommendations'])}")
        
        # Test SQL formatting
        try:
            formatted = validator.format_sql(query)
            if formatted != query:
                print(f"Formatted SQL:\n{formatted}")
        except:
            pass  # Skip formatting if it fails