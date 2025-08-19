"""Tests for the get_database_ddl module."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from collections import namedtuple
from src.metadata.get_database_ddl import (
    get_table_ddl,
    get_column_comments,
    get_primary_key_columns, 
    get_foreign_key_ddl,
    get_index_ddl,
    get_database_ddl,
    get_database_schema,
    main
)


class TestGetTableDDL:
    """Tests for get_table_ddl function."""
    
    def test_get_table_ddl_basic(self, mock_engine):
        """Test basic table DDL generation."""
        # Mock column data
        Column = namedtuple('Column', ['column_name', 'data_type', 'character_maximum_length', 
                                     'numeric_precision', 'numeric_scale', 'is_nullable', 'column_default'])
        mock_columns = [
            Column('id', 'integer', None, None, None, 'NO', 'nextval(\'seq\')'),
            Column('name', 'character varying', 255, None, None, 'NO', None),
            Column('email', 'character varying', 255, None, None, 'YES', None),
            Column('balance', 'numeric', None, 10, 2, 'YES', '0.00')
        ]
        
        # Create proper context manager mock
        context_manager = Mock()
        mock_conn = Mock()
        context_manager.__enter__ = Mock(return_value=mock_conn)
        context_manager.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = context_manager
        mock_conn.execute.return_value.fetchall.return_value = mock_columns
        
        # Mock primary key columns
        with patch('src.metadata.get_database_ddl.get_primary_key_columns', return_value=['id']):
            result = get_table_ddl(mock_engine, 'test_table')
        
        assert 'CREATE TABLE "public"."test_table"' in result
        assert '"id" INTEGER DEFAULT nextval(\'seq\') NOT NULL' in result
        assert '"name" VARCHAR(255) NOT NULL' in result
        assert '"email" VARCHAR(255)' in result  # nullable, no NOT NULL
        assert '"balance" NUMERIC(10,2) DEFAULT 0.00' in result
        assert 'CONSTRAINT "test_table_pkey" PRIMARY KEY ("id")' in result
    
    def test_get_table_ddl_no_columns(self, mock_engine):
        """Test get_table_ddl when no columns are returned."""
        # Create proper context manager mock
        context_manager = Mock()
        mock_conn = Mock()
        context_manager.__enter__ = Mock(return_value=mock_conn)
        context_manager.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = context_manager
        mock_conn.execute.return_value.fetchall.return_value = []
        
        result = get_table_ddl(mock_engine, 'empty_table')
        
        assert result == ""
    
    def test_get_table_ddl_no_primary_key(self, mock_engine):
        """Test get_table_ddl when table has no primary key."""
        Column = namedtuple('Column', ['column_name', 'data_type', 'character_maximum_length', 
                                     'numeric_precision', 'numeric_scale', 'is_nullable', 'column_default'])
        mock_columns = [
            Column('name', 'character varying', 255, None, None, 'NO', None)
        ]
        
        # Create proper context manager mock
        context_manager = Mock()
        mock_conn = Mock()
        context_manager.__enter__ = Mock(return_value=mock_conn)
        context_manager.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = context_manager
        mock_conn.execute.return_value.fetchall.return_value = mock_columns
        
        # Mock no primary key
        with patch('src.metadata.get_database_ddl.get_primary_key_columns', return_value=[]):
            result = get_table_ddl(mock_engine, 'no_pk_table')
        
        assert 'CREATE TABLE "public"."no_pk_table"' in result
        assert '"name" VARCHAR(255) NOT NULL' in result
        assert 'PRIMARY KEY' not in result
    
    def test_get_table_ddl_custom_schema(self, mock_engine):
        """Test get_table_ddl with custom schema."""
        Column = namedtuple('Column', ['column_name', 'data_type', 'character_maximum_length', 
                                     'numeric_precision', 'numeric_scale', 'is_nullable', 'column_default'])
        mock_columns = [
            Column('id', 'integer', None, None, None, 'NO', None)
        ]
        
        # Create proper context manager mock
        context_manager = Mock()
        mock_conn = Mock()
        context_manager.__enter__ = Mock(return_value=mock_conn)
        context_manager.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = context_manager
        mock_conn.execute.return_value.fetchall.return_value = mock_columns
        
        with patch('src.metadata.get_database_ddl.get_primary_key_columns', return_value=['id']):
            result = get_table_ddl(mock_engine, 'test_table', 'custom_schema')
        
        assert 'CREATE TABLE "custom_schema"."test_table"' in result


class TestGetColumnComments:
    """Tests for get_column_comments function."""
    
    def test_get_column_comments_success(self, mock_engine):
        """Test successful retrieval of column comments."""
        Comment = namedtuple('Comment', ['column_name', 'comment'])
        mock_comments = [
            Comment('id', 'Primary key identifier'),
            Comment('name', 'Customer name')
        ]
        
        # Create proper context manager mock
        context_manager = Mock()
        mock_conn = Mock()
        context_manager.__enter__ = Mock(return_value=mock_conn)
        context_manager.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = context_manager
        mock_conn.execute.return_value.fetchall.return_value = mock_comments
        
        result = get_column_comments(mock_engine, 'customers')
        
        assert len(result) == 2
        assert result[0] == ('id', 'Primary key identifier')
        assert result[1] == ('name', 'Customer name')
    
    def test_get_column_comments_no_comments(self, mock_engine):
        """Test get_column_comments when no comments exist."""
        # Create proper context manager mock
        context_manager = Mock()
        mock_conn = Mock()
        context_manager.__enter__ = Mock(return_value=mock_conn)
        context_manager.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = context_manager
        mock_conn.execute.return_value.fetchall.return_value = []
        
        result = get_column_comments(mock_engine, 'no_comments_table')
        
        assert result == []


class TestGetPrimaryKeyColumns:
    """Tests for get_primary_key_columns function."""
    
    def test_get_primary_key_columns_single(self, mock_engine):
        """Test getting single primary key column."""
        PK = namedtuple('PK', ['column_name'])
        mock_pk = [PK('id')]
        
        # Create proper context manager mock
        context_manager = Mock()
        mock_conn = Mock()
        context_manager.__enter__ = Mock(return_value=mock_conn)
        context_manager.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = context_manager
        mock_conn.execute.return_value.fetchall.return_value = mock_pk
        
        result = get_primary_key_columns(mock_engine, 'customers')
        
        assert result == ['id']
    
    def test_get_primary_key_columns_composite(self, mock_engine):
        """Test getting composite primary key columns."""
        PK = namedtuple('PK', ['column_name'])
        mock_pk = [PK('order_id'), PK('product_id')]
        
        # Create proper context manager mock
        context_manager = Mock()
        mock_conn = Mock()
        context_manager.__enter__ = Mock(return_value=mock_conn)
        context_manager.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = context_manager
        mock_conn.execute.return_value.fetchall.return_value = mock_pk
        
        result = get_primary_key_columns(mock_engine, 'order_items')
        
        assert result == ['order_id', 'product_id']
    
    def test_get_primary_key_columns_none(self, mock_engine):
        """Test getting primary key when none exists."""
        # Create proper context manager mock
        context_manager = Mock()
        mock_conn = Mock()
        context_manager.__enter__ = Mock(return_value=mock_conn)
        context_manager.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = context_manager
        mock_conn.execute.return_value.fetchall.return_value = []
        
        result = get_primary_key_columns(mock_engine, 'no_pk_table')
        
        assert result == []


class TestGetForeignKeyDDL:
    """Tests for get_foreign_key_ddl function."""
    
    def test_get_foreign_key_ddl_success(self, mock_engine):
        """Test successful foreign key DDL generation."""
        FK = namedtuple('FK', ['constraint_name', 'columns', 'foreign_table_schema', 'foreign_table_name', 'foreign_columns'])
        mock_fks = [
            FK('fk_orders_customer', 'customer_id', 'public', 'customers', 'customer_id'),
            FK('fk_orders_product', 'product_id', 'public', 'products', 'product_id')
        ]
        
        # Create proper context manager mock
        context_manager = Mock()
        mock_conn = Mock()
        context_manager.__enter__ = Mock(return_value=mock_conn)
        context_manager.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = context_manager
        mock_conn.execute.return_value.fetchall.return_value = mock_fks
        
        result = get_foreign_key_ddl(mock_engine, 'orders')
        
        assert len(result) == 2
        assert 'ALTER TABLE "public"."orders"' in result[0]
        assert 'REFERENCES "public"."customers"' in result[0]
        assert 'REFERENCES "public"."products"' in result[1]
    
    def test_get_foreign_key_ddl_no_fks(self, mock_engine):
        """Test get_foreign_key_ddl when no foreign keys exist."""
        # Create proper context manager mock
        context_manager = Mock()
        mock_conn = Mock()
        context_manager.__enter__ = Mock(return_value=mock_conn)
        context_manager.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = context_manager
        mock_conn.execute.return_value.fetchall.return_value = []
        
        result = get_foreign_key_ddl(mock_engine, 'standalone_table')
        
        assert result == []


class TestGetIndexDDL:
    """Tests for get_index_ddl function."""
    
    def test_get_index_ddl_success(self, mock_engine):
        """Test successful index DDL generation."""
        Index = namedtuple('Index', ['index_name', 'indisunique', 'columns'])
        mock_indexes = [
            Index('idx_customer_email', False, 'email'),
            Index('idx_customer_name_unique', True, 'customer_name')
        ]
        
        # Create proper context manager mock
        context_manager = Mock()
        mock_conn = Mock()
        context_manager.__enter__ = Mock(return_value=mock_conn)
        context_manager.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = context_manager
        mock_conn.execute.return_value.fetchall.return_value = mock_indexes
        
        result = get_index_ddl(mock_engine, 'customers')
        
        assert len(result) == 2
        assert 'CREATE INDEX "idx_customer_email"' in result[0]
        assert 'CREATE UNIQUE INDEX "idx_customer_name_unique"' in result[1]
    
    def test_get_index_ddl_no_indexes(self, mock_engine):
        """Test get_index_ddl when no indexes exist."""
        # Create proper context manager mock
        context_manager = Mock()
        mock_conn = Mock()
        context_manager.__enter__ = Mock(return_value=mock_conn)
        context_manager.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = context_manager
        mock_conn.execute.return_value.fetchall.return_value = []
        
        result = get_index_ddl(mock_engine, 'no_indexes_table')
        
        assert result == []


class TestGetDatabaseDDL:
    """Tests for get_database_ddl function."""
    
    @patch('src.metadata.get_database_ddl.get_db_connection')
    @patch('src.metadata.get_database_ddl.get_table_ddl')
    @patch('src.metadata.get_database_ddl.get_foreign_key_ddl')
    @patch('src.metadata.get_database_ddl.get_index_ddl')
    def test_get_database_ddl_success(self, mock_get_index, mock_get_fk, mock_get_table, mock_get_connection):
        """Test successful complete database DDL generation."""
        # Setup mocks
        mock_engine = Mock()
        mock_get_connection.return_value = mock_engine
        
        # Mock table list
        Table = namedtuple('Table', ['table_name'])
        mock_tables = [Table('customers'), Table('orders')]
        # Create proper context manager mock
        context_manager = Mock()
        mock_conn = Mock()
        context_manager.__enter__ = Mock(return_value=mock_conn)
        context_manager.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = context_manager
        mock_conn.execute.return_value.fetchall.return_value = mock_tables
        
        # Mock DDL functions
        mock_get_table.side_effect = [
            'CREATE TABLE customers (...);',
            'CREATE TABLE orders (...);'
        ]
        mock_get_fk.side_effect = [
            ['ALTER TABLE customers ADD CONSTRAINT ...;'],
            ['ALTER TABLE orders ADD CONSTRAINT ...;']
        ]
        mock_get_index.side_effect = [
            ['CREATE INDEX idx_customer ...;'],
            ['CREATE INDEX idx_order ...;']
        ]
        
        result = get_database_ddl()
        
        # Verify structure
        assert '-- Table: customers' in result
        assert '-- Table: orders' in result
        assert '-- Foreign Keys for: customers' in result
        assert '-- Indexes for: customers' in result
        assert 'CREATE TABLE customers' in result
        assert 'CREATE TABLE orders' in result
        assert 'ALTER TABLE customers ADD CONSTRAINT' in result
        assert 'CREATE INDEX idx_customer' in result
    
    @patch('src.metadata.get_database_ddl.get_db_connection')
    def test_get_database_ddl_no_tables(self, mock_get_connection):
        """Test get_database_ddl when no tables exist."""
        mock_engine = Mock()
        mock_get_connection.return_value = mock_engine
        
        # Create proper context manager mock
        context_manager = Mock()
        mock_conn = Mock()
        context_manager.__enter__ = Mock(return_value=mock_conn)
        context_manager.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = context_manager
        mock_conn.execute.return_value.fetchall.return_value = []
        
        result = get_database_ddl()
        
        assert result == ""
    
    @patch('src.metadata.get_database_ddl.get_db_connection')
    def test_get_database_ddl_custom_schema(self, mock_get_connection):
        """Test get_database_ddl with custom schema."""
        mock_engine = Mock()
        mock_get_connection.return_value = mock_engine
        
        # Create proper context manager mock
        context_manager = Mock()
        mock_conn = Mock()
        context_manager.__enter__ = Mock(return_value=mock_conn)
        context_manager.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = context_manager
        mock_conn.execute.return_value.fetchall.return_value = []
        
        get_database_ddl('custom_schema')
        
        # Verify custom schema was used in query
        call_args = mock_conn.execute.call_args
        assert 'custom_schema' in str(call_args)


class TestGetDatabaseSchema:
    """Tests for get_database_schema function."""
    
    @patch('src.metadata.get_database_ddl.get_db_connection')
    def test_get_database_schema_success(self, mock_get_connection):
        """Test successful database schema retrieval."""
        mock_engine = Mock()
        mock_get_connection.return_value = mock_engine
        
        # Mock table list
        Table = namedtuple('Table', ['table_name'])
        mock_tables = [Table('customers'), Table('orders')]
        
        # Create a proper context manager mock
        context_manager = Mock()
        mock_conn = Mock()
        context_manager.__enter__ = Mock(return_value=mock_conn)
        context_manager.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = context_manager
        
        mock_conn.execute.return_value.fetchall.side_effect = [
            mock_tables,  # First call for tables
            # Mock column info for customers
            [('customer_id', 'varchar', 255, None, None, 'NO', None, 'Customer identifier'),
             ('name', 'varchar', 100, None, None, 'NO', None, 'Customer name')],
            # Mock PK info for customers  
            [('customer_id',)],
            # Mock FK info for customers
            [('fk_orders_customer', 'customer_id', 'public', 'orders', 'customer_id')],
            # Mock column info for orders  
            [('order_id', 'varchar', 255, None, None, 'NO', None, 'Order identifier'),
             ('customer_id', 'varchar', 255, None, None, 'NO', None, 'Customer reference')],
            # Mock PK info for orders
            [('order_id',)],
            # Mock FK info for orders
            []
        ]
        
        result = get_database_schema()
        
        assert 'tables' in result
        assert len(result['tables']) == 2
        
        # Check customers table
        customers_table = result['tables'][0]
        assert customers_table['name'] == 'customers'
        assert len(customers_table['columns']) == 2
        assert customers_table['columns'][0]['name'] == 'customer_id'
        assert customers_table['columns'][0]['description'] == 'Customer identifier'
        
        # Check foreign keys
        assert len(customers_table['foreign_keys']) == 1
        assert customers_table['foreign_keys'][0]['name'] == 'fk_orders_customer'
    
    @patch('src.metadata.get_database_ddl.get_db_connection')
    def test_get_database_schema_no_tables(self, mock_get_connection):
        """Test get_database_schema when no tables exist."""
        mock_engine = Mock()
        mock_get_connection.return_value = mock_engine
        
        # Create a proper context manager mock
        context_manager = Mock()
        mock_conn = Mock()
        context_manager.__enter__ = Mock(return_value=mock_conn)
        context_manager.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = context_manager
        
        mock_conn.execute.return_value.fetchall.return_value = []
        
        result = get_database_schema()
        
        assert result == {'tables': []}


class TestMainFunction:
    """Tests for the main function."""
    
    @patch('src.metadata.get_database_ddl.get_database_ddl')
    @patch('src.metadata.get_database_ddl.get_database_schema')
    @patch('builtins.print')
    def test_main_success(self, mock_print, mock_get_schema, mock_get_ddl):
        """Test successful main function execution."""
        mock_get_ddl.return_value = "CREATE TABLE test (...)"
        mock_get_schema.return_value = {
            'tables': [
                {
                    'schema': 'public',
                    'name': 'test_table',
                    'columns': [{'name': 'id', 'data_type': 'INTEGER', 'is_nullable': False, 'description': 'ID'}],
                    'primary_key': {'name': 'test_table_pkey', 'columns': ['id']},
                    'foreign_keys': []
                }
            ]
        }
        
        main()
        
        mock_get_ddl.assert_called_once()
        # The main function prints both DDL and schema, so we just check that print was called
        assert mock_print.call_count > 0
    
    @patch('src.metadata.get_database_ddl.get_database_ddl')
    @patch('src.metadata.get_database_ddl.get_database_schema')
    @patch('builtins.print')
    def test_main_empty_ddl(self, mock_print, mock_get_schema, mock_get_ddl):
        """Test main function with empty DDL result."""
        mock_get_ddl.return_value = ""
        mock_get_schema.return_value = {'tables': []}
        
        main()
        
        mock_get_ddl.assert_called_once()
        mock_get_schema.assert_called_once()
        # The main function prints both DDL and schema, so we check that print was called
        assert mock_print.call_count > 0


class TestDataTypeFormatting:
    """Tests for data type formatting logic in get_table_ddl."""
    
    def test_character_varying_with_length(self, mock_engine):
        """Test character varying type with length formatting."""
        Column = namedtuple('Column', ['column_name', 'data_type', 'character_maximum_length', 
                                     'numeric_precision', 'numeric_scale', 'is_nullable', 'column_default'])
        mock_columns = [
            Column('name', 'character varying', 255, None, None, 'NO', None)
        ]
        
        # Create proper context manager mock
        context_manager = Mock()
        mock_conn = Mock()
        context_manager.__enter__ = Mock(return_value=mock_conn)
        context_manager.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = context_manager
        mock_conn.execute.return_value.fetchall.return_value = mock_columns
        
        with patch('src.metadata.get_database_ddl.get_primary_key_columns', return_value=[]):
            result = get_table_ddl(mock_engine, 'test_table')
        
        assert 'VARCHAR(255)' in result
    
    def test_numeric_with_precision_and_scale(self, mock_engine):
        """Test numeric type with precision and scale formatting."""
        Column = namedtuple('Column', ['column_name', 'data_type', 'character_maximum_length', 
                                     'numeric_precision', 'numeric_scale', 'is_nullable', 'column_default'])
        mock_columns = [
            Column('price', 'numeric', None, 10, 2, 'NO', None)
        ]
        
        # Create proper context manager mock
        context_manager = Mock()
        mock_conn = Mock()
        context_manager.__enter__ = Mock(return_value=mock_conn)
        context_manager.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = context_manager
        mock_conn.execute.return_value.fetchall.return_value = mock_columns
        
        with patch('src.metadata.get_database_ddl.get_primary_key_columns', return_value=[]):
            result = get_table_ddl(mock_engine, 'test_table')
        
        assert 'NUMERIC(10,2)' in result
    
    def test_text_type_no_length(self, mock_engine):
        """Test text type without length specification."""
        Column = namedtuple('Column', ['column_name', 'data_type', 'character_maximum_length', 
                                     'numeric_precision', 'numeric_scale', 'is_nullable', 'column_default'])
        mock_columns = [
            Column('description', 'text', None, None, None, 'YES', None)
        ]
        
        # Create proper context manager mock
        context_manager = Mock()
        mock_conn = Mock()
        context_manager.__enter__ = Mock(return_value=mock_conn)
        context_manager.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = context_manager
        mock_conn.execute.return_value.fetchall.return_value = mock_columns
        
        with patch('src.metadata.get_database_ddl.get_primary_key_columns', return_value=[]):
            result = get_table_ddl(mock_engine, 'test_table')
        
        assert '"description" TEXT' in result
        assert 'NOT NULL' not in result  # Should be nullable


class TestErrorHandling:
    """Tests for error handling scenarios."""
    
    @patch('src.metadata.get_database_ddl.get_db_connection')
    def test_database_connection_error(self, mock_get_connection):
        """Test handling of database connection errors."""
        mock_get_connection.side_effect = Exception("Connection failed")
        
        with pytest.raises(Exception, match="Connection failed"):
            get_database_ddl()
    
    def test_table_ddl_query_error(self, mock_engine):
        """Test handling of query execution errors in get_table_ddl."""
        # Create proper context manager mock
        context_manager = Mock()
        mock_conn = Mock()
        context_manager.__enter__ = Mock(return_value=mock_conn)
        context_manager.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = context_manager
        mock_conn.execute.side_effect = Exception("Query failed")
        
        with pytest.raises(Exception, match="Query failed"):
            get_table_ddl(mock_engine, 'test_table')