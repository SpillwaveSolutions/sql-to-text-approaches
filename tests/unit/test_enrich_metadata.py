"""Tests for the enrich_metadata module."""
import pytest
from unittest.mock import Mock, patch, MagicMock
import os
from src.metadata.enrich_metadata import (
    get_table_columns,
    get_foreign_key_info,
    generate_column_description,
    update_column_description,
    enrich_metadata
)


class TestGetTableColumns:
    """Tests for get_table_columns function."""
    
    def test_get_table_columns_success(self, mock_engine):
        """Test successful retrieval of table columns."""
        # Mock the database response
        mock_result = [
            ('customer_id', 'character varying', False, 'Unique customer identifier'),
            ('customer_name', 'character varying', False, ''),
            ('email', 'character varying', True, 'Customer email address')
        ]
        mock_engine.connect.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = mock_result
        
        result = get_table_columns(mock_engine, 'customers')
        
        assert len(result) == 3
        assert result[0] == ('customer_id', 'character varying', False, 'Unique customer identifier')
        assert result[1] == ('customer_name', 'character varying', False, '')
        assert result[2] == ('email', 'character varying', True, 'Customer email address')
        
        # Verify the SQL query was executed
        mock_engine.connect.return_value.__enter__.return_value.execute.assert_called_once()
    
    def test_get_table_columns_with_custom_schema(self, mock_engine):
        """Test get_table_columns with custom schema."""
        mock_result = [('id', 'integer', False, '')]
        mock_engine.connect.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = mock_result
        
        result = get_table_columns(mock_engine, 'test_table', 'custom_schema')
        
        assert len(result) == 1
        # Verify schema parameter was used in the query
        call_args = mock_engine.connect.return_value.__enter__.return_value.execute.call_args
        assert 'custom_schema' in str(call_args)
    
    def test_get_table_columns_empty_result(self, mock_engine):
        """Test get_table_columns with no columns returned."""
        mock_engine.connect.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = []
        
        result = get_table_columns(mock_engine, 'nonexistent_table')
        
        assert result == []


class TestGetForeignKeyInfo:
    """Tests for get_foreign_key_info function."""
    
    def test_get_foreign_key_info_success(self, mock_engine):
        """Test successful retrieval of foreign key information."""
        mock_result = [
            ('fk_orders_customer', 'orders', 'customer_id', 'customers', 'customer_id'),
            ('fk_orders_product', 'orders', 'product_id', 'products', 'product_id')
        ]
        mock_engine.connect.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = mock_result
        
        result = get_foreign_key_info(mock_engine, 'orders')
        
        assert len(result) == 2
        assert result[0] == {
            "fk_name": "fk_orders_customer",
            "parent_table": "orders",
            "parent_column": "customer_id", 
            "referenced_table": "customers",
            "referenced_column": "customer_id"
        }
    
    def test_get_foreign_key_info_no_relationships(self, mock_engine):
        """Test get_foreign_key_info with no foreign keys."""
        mock_engine.connect.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = []
        
        result = get_foreign_key_info(mock_engine, 'standalone_table')
        
        assert result == []


class TestGenerateColumnDescription:
    """Tests for generate_column_description function."""
    
    @patch('src.metadata.enrich_metadata.OpenAI')
    def test_generate_column_description_success(self, mock_openai_class):
        """Test successful generation of column description."""
        # Setup mock OpenAI client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "This is a generated column description."
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client
        
        fk_info = [{
            "parent_table": "orders",
            "parent_column": "customer_id",
            "referenced_table": "customers", 
            "referenced_column": "customer_id"
        }]
        
        result = generate_column_description(
            "orders", "customer_id", "character varying", False, fk_info, ""
        )
        
        assert result == "This is a generated column description."
        mock_client.chat.completions.create.assert_called_once()
    
    @patch('src.metadata.enrich_metadata.OpenAI')
    def test_generate_column_description_with_existing(self, mock_openai_class):
        """Test generate_column_description with existing description."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Enhanced description."
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client
        
        result = generate_column_description(
            "customers", "email", "varchar", True, [], "Existing email description"
        )
        
        assert result == "Enhanced description."
        # Verify the existing description was included in the prompt
        call_args = mock_client.chat.completions.create.call_args
        prompt_content = call_args[1]['messages'][1]['content']
        assert "Existing email description" in prompt_content
    
    @patch('src.metadata.enrich_metadata.OpenAI')
    def test_generate_column_description_api_error(self, mock_openai_class):
        """Test generate_column_description when OpenAI API fails."""
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        mock_openai_class.return_value = mock_client
        
        result = generate_column_description(
            "table", "column", "varchar", False, [], "existing desc"
        )
        
        assert result == "existing desc"
    
    @patch('src.metadata.enrich_metadata.OpenAI')
    def test_generate_column_description_no_existing_desc_on_error(self, mock_openai_class):
        """Test generate_column_description error handling with no existing description."""
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        mock_openai_class.return_value = mock_client
        
        result = generate_column_description(
            "table", "column", "varchar", False, [], ""
        )
        
        assert result == ""

    def test_generate_column_description_foreign_key_context(self):
        """Test that foreign key context is properly included in prompts."""
        with patch('src.metadata.enrich_metadata.OpenAI') as mock_openai_class:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "Description with FK context."
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai_class.return_value = mock_client
            
            fk_info = [{
                "parent_table": "orders",
                "parent_column": "customer_id", 
                "referenced_table": "customers",
                "referenced_column": "customer_id"
            }]
            
            generate_column_description(
                "orders", "customer_id", "varchar", False, fk_info, ""
            )
            
            # Verify FK info was included in the prompt
            call_args = mock_client.chat.completions.create.call_args
            prompt_content = call_args[1]['messages'][1]['content']
            assert "foreign key referencing customers.customer_id" in prompt_content


class TestUpdateColumnDescription:
    """Tests for update_column_description function."""
    
    def test_update_column_description_success(self, mock_engine):
        """Test successful update of column description."""
        mock_conn = mock_engine.connect.return_value.__enter__.return_value
        
        update_column_description(
            mock_engine, "customers", "email", "Customer email address"
        )
        
        # Verify the COMMENT ON COLUMN query was executed
        mock_conn.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
    
    def test_update_column_description_escapes_quotes(self, mock_engine):
        """Test that single quotes in description are properly escaped."""
        mock_conn = mock_engine.connect.return_value.__enter__.return_value
        
        description_with_quotes = "Customer's email address"
        update_column_description(
            mock_engine, "customers", "email", description_with_quotes
        )
        
        # Verify execute was called (escaping happens in the function)
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        # The escaped description should be in the parameters
        assert "Customer''s email address" in str(call_args)
    
    def test_update_column_description_custom_schema(self, mock_engine):
        """Test update_column_description with custom schema."""
        mock_conn = mock_engine.connect.return_value.__enter__.return_value
        
        update_column_description(
            mock_engine, "test_table", "test_column", "Test description", "custom_schema"
        )
        
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        # Verify custom schema was used in the query
        assert "custom_schema" in str(call_args[0][0])


class TestEnrichMetadata:
    """Tests for the main enrich_metadata function."""
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'})
    @patch('src.metadata.enrich_metadata.get_db_connection')
    @patch('src.metadata.enrich_metadata.get_foreign_key_info')
    @patch('src.metadata.enrich_metadata.get_table_columns')
    @patch('src.metadata.enrich_metadata.generate_column_description')
    @patch('src.metadata.enrich_metadata.update_column_description')
    def test_enrich_metadata_success(
        self, mock_update, mock_generate, mock_get_columns, 
        mock_get_fks, mock_get_connection
    ):
        """Test successful metadata enrichment."""
        # Setup mocks
        mock_engine = Mock()
        mock_get_connection.return_value = mock_engine
        
        # Mock table list using context manager
        context_manager = Mock()
        mock_conn = Mock()
        context_manager.__enter__ = Mock(return_value=mock_conn)
        context_manager.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = context_manager
        mock_conn.execute.return_value.fetchall.return_value = [('customers',), ('orders',)]
        
        # Mock foreign key info
        mock_get_fks.return_value = []
        
        # Mock column info
        mock_get_columns.return_value = [
            ('customer_id', 'varchar', False, ''),
            ('email', 'varchar', True, 'Email address')
        ]
        
        # Mock description generation (need enough values for all columns)
        mock_generate.side_effect = [
            'Generated description for customer_id',
            'Generated description for email',
            'Generated description for customer_id',  # For orders table
            'Generated description for email'         # For orders table
        ]
        
        enrich_metadata()
        
        # Verify the process was called for each table and column
        assert mock_get_fks.call_count == 2  # Called for each table
        assert mock_get_columns.call_count == 2  # Called for each table
        assert mock_generate.call_count == 4  # Called for each column (2 tables × 2 columns)
        assert mock_update.call_count == 4  # Called for each column
    
    def test_enrich_metadata_missing_api_key(self):
        """Test enrich_metadata raises error when OPENAI_API_KEY is missing."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="OPENAI_API_KEY environment variable must be set"):
                enrich_metadata()
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'})
    @patch('src.metadata.enrich_metadata.get_db_connection')
    @patch('src.metadata.enrich_metadata.get_foreign_key_info')
    @patch('src.metadata.enrich_metadata.get_table_columns')
    @patch('src.metadata.enrich_metadata.generate_column_description')
    @patch('src.metadata.enrich_metadata.update_column_description')
    def test_enrich_metadata_skips_empty_descriptions(
        self, mock_update, mock_generate, mock_get_columns, 
        mock_get_fks, mock_get_connection
    ):
        """Test that empty descriptions are not updated."""
        # Setup mocks
        mock_engine = Mock()
        mock_get_connection.return_value = mock_engine
        
        # Mock table list
        context_manager = Mock()
        mock_conn = Mock()
        context_manager.__enter__ = Mock(return_value=mock_conn)
        context_manager.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = context_manager
        mock_conn.execute.return_value.fetchall.return_value = [('test_table',)]
        
        mock_get_fks.return_value = []
        mock_get_columns.return_value = [('test_column', 'varchar', False, '')]
        
        # Mock empty description generation
        mock_generate.return_value = ""
        
        enrich_metadata()
        
        # Verify update was not called for empty description
        mock_update.assert_not_called()
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'})
    @patch('src.metadata.enrich_metadata.get_db_connection')
    def test_enrich_metadata_custom_schema(self, mock_get_connection):
        """Test enrich_metadata with custom schema."""
        mock_engine = Mock()
        mock_get_connection.return_value = mock_engine
        
        # Mock empty table list to avoid further processing
        context_manager = Mock()
        mock_conn = Mock()
        context_manager.__enter__ = Mock(return_value=mock_conn)
        context_manager.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = context_manager
        mock_conn.execute.return_value.fetchall.return_value = []
        
        enrich_metadata('custom_schema')
        
        # Verify the custom schema was used in the table query
        call_args = mock_conn.execute.call_args
        assert 'custom_schema' in str(call_args)


class TestIntegration:
    """Integration tests that test multiple functions together."""
    
    @patch('src.metadata.enrich_metadata.OpenAI')
    def test_full_column_enrichment_flow(self, mock_openai_class, mock_engine):
        """Test the full flow from getting columns to updating descriptions."""
        # Setup OpenAI mock
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Enhanced column description."
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client
        
        # Setup database mocks with proper context manager
        context_manager = Mock()
        mock_conn = Mock()
        context_manager.__enter__ = Mock(return_value=mock_conn)
        context_manager.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = context_manager
        
        # Mock get_table_columns response (4 elements per row as expected by the function)
        column_data = [('email', 'varchar', True, 'Old description')]
        
        # Mock get_foreign_key_info response (5 elements per row as expected by the function)
        fk_data = []  # Empty list to avoid IndexError
        
        # Set up side effects for different calls
        mock_conn.execute.return_value.fetchall.side_effect = [
            column_data,  # For get_table_columns
            fk_data       # For get_foreign_key_info
        ]
        
        # Test the flow
        columns = get_table_columns(mock_engine, 'customers')
        fk_info = get_foreign_key_info(mock_engine, 'customers')  # Will return empty list from mock
        
        for column_name, data_type, is_nullable, existing_desc in columns:
            description = generate_column_description(
                'customers', column_name, data_type, is_nullable, fk_info, existing_desc
            )
            update_column_description(mock_engine, 'customers', column_name, description)
        
        # Verify the full flow executed
        assert len(columns) == 1
        mock_client.chat.completions.create.assert_called_once()
        assert mock_conn.execute.call_count >= 2  # At least get columns and update description