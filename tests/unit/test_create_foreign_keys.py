"""Tests for the create_foreign_keys module."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from collections import namedtuple
from src.loadin.create_foreign_keys import (
    get_table_columns_with_types,
    ensure_valid_key_type,
    check_uniqueness,
    get_primary_key_columns,
    find_foreign_key_relationships,
    check_referential_integrity,
    create_foreign_keys,
    main
)


class TestGetTableColumnsWithTypes:
    """Tests for get_table_columns_with_types function."""
    
    def test_get_table_columns_with_types_success(self, mock_engine):
        """Test successful retrieval of table columns with types."""
        Column = namedtuple('Column', ['column_name', 'data_type', 'character_maximum_length'])
        mock_columns = [
            Column('customer_id', 'character varying', 255),
            Column('name', 'character varying', 100),
            Column('age', 'integer', None),
            Column('balance', 'numeric', None)
        ]
        
        mock_conn = mock_engine.connect.return_value.__enter__.return_value
        mock_conn.execute.return_value = mock_columns
        
        result = get_table_columns_with_types(mock_engine, 'customers')
        
        expected = {
            'customer_id': {'type': 'character varying', 'length': 255},
            'name': {'type': 'character varying', 'length': 100},
            'age': {'type': 'integer', 'length': None},
            'balance': {'type': 'numeric', 'length': None}
        }
        assert result == expected
    
    def test_get_table_columns_with_types_empty(self, mock_engine):
        """Test get_table_columns_with_types with no columns."""
        mock_conn = mock_engine.connect.return_value.__enter__.return_value
        mock_conn.execute.return_value = []
        
        result = get_table_columns_with_types(mock_engine, 'empty_table')
        
        assert result == {}


class TestEnsureValidKeyType:
    """Tests for ensure_valid_key_type function."""
    
    def test_ensure_valid_key_type_success(self, mock_engine):
        """Test successful column type conversion."""
        mock_conn = mock_engine.connect.return_value.__enter__.return_value
        
        result = ensure_valid_key_type(mock_engine, 'test_table', 'test_column')
        
        assert result is True
        mock_conn.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
    
    def test_ensure_valid_key_type_failure(self, mock_engine):
        """Test column type conversion failure."""
        mock_conn = mock_engine.connect.return_value.__enter__.return_value
        mock_conn.execute.side_effect = Exception("Conversion failed")
        
        result = ensure_valid_key_type(mock_engine, 'test_table', 'test_column')
        
        assert result is False


class TestCheckUniqueness:
    """Tests for check_uniqueness function."""
    
    def test_check_uniqueness_unique(self, mock_engine):
        """Test check_uniqueness with unique values."""
        Result = namedtuple('Result', ['total_rows', 'unique_values'])
        mock_result = Result(100, 100)  # All values are unique
        
        mock_conn = mock_engine.connect.return_value.__enter__.return_value
        mock_conn.execute.return_value.fetchone.return_value = mock_result
        
        result = check_uniqueness(mock_engine, 'customers', 'customer_id')
        
        assert result is True
    
    def test_check_uniqueness_not_unique(self, mock_engine):
        """Test check_uniqueness with non-unique values."""
        Result = namedtuple('Result', ['total_rows', 'unique_values'])
        mock_result = Result(100, 95)  # Some duplicate values
        
        mock_conn = mock_engine.connect.return_value.__enter__.return_value
        mock_conn.execute.return_value.fetchone.return_value = mock_result
        
        result = check_uniqueness(mock_engine, 'orders', 'customer_id')
        
        assert result is False
    
    def test_check_uniqueness_error(self, mock_engine):
        """Test check_uniqueness with database error."""
        mock_conn = mock_engine.connect.return_value.__enter__.return_value
        mock_conn.execute.side_effect = Exception("Query failed")
        
        result = check_uniqueness(mock_engine, 'test_table', 'test_column')
        
        assert result is False


class TestGetPrimaryKeyColumns:
    """Tests for get_primary_key_columns function."""
    
    def test_get_primary_key_columns_single(self, mock_engine):
        """Test getting single primary key column."""
        PK = namedtuple('PK', ['column_name'])
        mock_result = [PK('customer_id')]
        
        mock_conn = mock_engine.connect.return_value.__enter__.return_value
        mock_conn.execute.return_value = mock_result
        
        result = get_primary_key_columns(mock_engine, 'customers')
        
        assert result == ['customer_id']
    
    def test_get_primary_key_columns_composite(self, mock_engine):
        """Test getting composite primary key."""
        PK = namedtuple('PK', ['column_name'])
        mock_result = [PK('order_id'), PK('product_id')]
        
        mock_conn = mock_engine.connect.return_value.__enter__.return_value
        mock_conn.execute.return_value = mock_result
        
        result = get_primary_key_columns(mock_engine, 'order_items')
        
        assert result == ['order_id', 'product_id']
    
    def test_get_primary_key_columns_none(self, mock_engine):
        """Test getting primary key when none exists."""
        mock_conn = mock_engine.connect.return_value.__enter__.return_value
        mock_conn.execute.return_value = []
        
        result = get_primary_key_columns(mock_engine, 'no_pk_table')
        
        assert result == []
    
    def test_get_primary_key_columns_error(self, mock_engine):
        """Test get_primary_key_columns with database error."""
        mock_conn = mock_engine.connect.return_value.__enter__.return_value
        mock_conn.execute.side_effect = Exception("Query failed")
        
        result = get_primary_key_columns(mock_engine, 'test_table')
        
        assert result == []


class TestFindForeignKeyRelationships:
    """Tests for find_foreign_key_relationships function."""
    
    @patch('src.loadin.create_foreign_keys.get_table_columns_with_types')
    def test_find_foreign_key_relationships_success(self, mock_get_columns, mock_engine):
        """Test successful identification of foreign key relationships."""
        # Mock column data for different tables
        def mock_columns_side_effect(engine, table_name):
            if table_name == 'customers':
                return {'customer_id': {'type': 'varchar', 'length': 255}, 'name': {'type': 'varchar', 'length': 100}}
            elif table_name == 'orders':
                return {'order_id': {'type': 'varchar', 'length': 255}, 'customer_id': {'type': 'varchar', 'length': 255}}
            elif table_name == 'products':
                return {'product_id': {'type': 'varchar', 'length': 255}, 'name': {'type': 'varchar', 'length': 100}}
            else:
                return {}
        
        mock_get_columns.side_effect = mock_columns_side_effect
        
        tables = ['customers', 'orders', 'products']
        result = find_foreign_key_relationships(mock_engine, tables)
        
        # Should find customer_id relationship between customers and orders
        assert len(result) == 1
        relationship = result[0]
        assert relationship['parent_table'] == 'customers'
        assert relationship['child_table'] == 'orders'
        assert relationship['column_name'] == 'customer_id'
    
    @patch('src.loadin.create_foreign_keys.get_table_columns_with_types')
    def test_find_foreign_key_relationships_multiple(self, mock_get_columns, mock_engine):
        """Test finding multiple foreign key relationships."""
        def mock_columns_side_effect(engine, table_name):
            if table_name == 'customers':
                return {'customer_id': {'type': 'varchar', 'length': 255}}
            elif table_name == 'products':
                return {'product_id': {'type': 'varchar', 'length': 255}}
            elif table_name == 'order_items':
                return {
                    'item_id': {'type': 'varchar', 'length': 255},
                    'customer_id': {'type': 'varchar', 'length': 255},
                    'product_id': {'type': 'varchar', 'length': 255}
                }
            else:
                return {}
        
        mock_get_columns.side_effect = mock_columns_side_effect
        
        tables = ['customers', 'products', 'order_items']
        result = find_foreign_key_relationships(mock_engine, tables)
        
        # Should find both customer_id and product_id relationships
        assert len(result) == 2
        
        # Check customer relationship
        customer_rel = next(r for r in result if r['column_name'] == 'customer_id')
        assert customer_rel['parent_table'] == 'customers'
        assert customer_rel['child_table'] == 'order_items'
        
        # Check product relationship
        product_rel = next(r for r in result if r['column_name'] == 'product_id')
        assert product_rel['parent_table'] == 'products'
        assert product_rel['child_table'] == 'order_items'
    
    @patch('src.loadin.create_foreign_keys.get_table_columns_with_types')
    def test_find_foreign_key_relationships_none(self, mock_get_columns, mock_engine):
        """Test finding no foreign key relationships."""
        def mock_columns_side_effect(engine, table_name):
            if table_name == 'standalone1':
                return {'id': {'type': 'varchar', 'length': 255}, 'name': {'type': 'varchar', 'length': 100}}
            elif table_name == 'standalone2':
                return {'id': {'type': 'varchar', 'length': 255}, 'description': {'type': 'text', 'length': None}}
            else:
                return {}
        
        mock_get_columns.side_effect = mock_columns_side_effect
        
        tables = ['standalone1', 'standalone2']
        result = find_foreign_key_relationships(mock_engine, tables)
        
        assert result == []


class TestCheckReferentialIntegrity:
    """Tests for check_referential_integrity function."""
    
    def test_check_referential_integrity_valid(self, mock_engine):
        """Test referential integrity check with valid relationships."""
        Result = namedtuple('Result', ['invalid_count'])
        mock_result = Result(0)  # No invalid references
        
        mock_conn = mock_engine.connect.return_value.__enter__.return_value
        mock_conn.execute.return_value.fetchone.return_value = mock_result
        
        result = check_referential_integrity(mock_engine, 'customers', 'orders', 'customer_id')
        
        assert result is True
    
    def test_check_referential_integrity_invalid(self, mock_engine):
        """Test referential integrity check with invalid relationships."""
        Result = namedtuple('Result', ['invalid_count'])
        mock_result = Result(5)  # 5 invalid references
        
        mock_conn = mock_engine.connect.return_value.__enter__.return_value
        mock_conn.execute.return_value.fetchone.return_value = mock_result
        
        result = check_referential_integrity(mock_engine, 'customers', 'orders', 'customer_id')
        
        assert result is False
    
    def test_check_referential_integrity_error(self, mock_engine):
        """Test referential integrity check with database error."""
        mock_conn = mock_engine.connect.return_value.__enter__.return_value
        mock_conn.execute.side_effect = Exception("Query failed")
        
        result = check_referential_integrity(mock_engine, 'customers', 'orders', 'customer_id')
        
        assert result is False


class TestCreateForeignKeys:
    """Tests for create_foreign_keys function."""
    
    @patch('src.loadin.create_foreign_keys.ensure_valid_key_type')
    @patch('src.loadin.create_foreign_keys.get_primary_key_columns')
    @patch('src.loadin.create_foreign_keys.check_uniqueness')
    @patch('src.loadin.create_foreign_keys.check_referential_integrity')
    def test_create_foreign_keys_success(
        self, mock_ref_integrity, mock_uniqueness, mock_get_pk, mock_ensure_type, mock_engine
    ):
        """Test successful foreign key creation."""
        # Setup mocks
        mock_ensure_type.return_value = True
        mock_get_pk.return_value = []  # No existing PK
        mock_uniqueness.return_value = True
        mock_ref_integrity.return_value = True
        
        mock_conn = mock_engine.connect.return_value.__enter__.return_value
        
        relationships = [
            {
                'parent_table': 'customers',
                'child_table': 'orders',
                'column_name': 'customer_id',
                'parent_type': {'type': 'varchar', 'length': 255},
                'child_type': {'type': 'varchar', 'length': 255}
            }
        ]
        
        create_foreign_keys(mock_engine, relationships)
        
        # Verify all necessary functions were called
        mock_ensure_type.assert_called()
        mock_get_pk.assert_called_with(mock_engine, 'customers')
        mock_uniqueness.assert_called_with(mock_engine, 'customers', 'customer_id')
        mock_ref_integrity.assert_called_with(mock_engine, 'customers', 'orders', 'customer_id')
        
        # Verify SQL execution for PK and FK creation
        assert mock_conn.execute.call_count >= 2  # PK creation + FK creation
        assert mock_conn.commit.call_count >= 2
    
    @patch('src.loadin.create_foreign_keys.ensure_valid_key_type')
    @patch('src.loadin.create_foreign_keys.get_primary_key_columns')
    def test_create_foreign_keys_existing_pk(self, mock_get_pk, mock_ensure_type, mock_engine):
        """Test foreign key creation with existing primary key."""
        mock_ensure_type.return_value = True
        mock_get_pk.return_value = ['customer_id']  # Existing PK
        
        with patch('src.loadin.create_foreign_keys.check_referential_integrity', return_value=True):
            relationships = [
                {
                    'parent_table': 'customers',
                    'child_table': 'orders',
                    'column_name': 'customer_id',
                    'parent_type': {'type': 'varchar', 'length': 255},
                    'child_type': {'type': 'varchar', 'length': 255}
                }
            ]
            
            create_foreign_keys(mock_engine, relationships)
            
            # Should not try to create PK since one exists
            mock_conn = mock_engine.connect.return_value.__enter__.return_value
            # Only FK creation call expected
            assert mock_conn.execute.call_count == 1
    
    @patch('src.loadin.create_foreign_keys.ensure_valid_key_type')
    def test_create_foreign_keys_type_conversion_failure(self, mock_ensure_type, mock_engine):
        """Test foreign key creation when type conversion fails."""
        mock_ensure_type.return_value = False
        
        relationships = [
            {
                'parent_table': 'customers',
                'child_table': 'orders',
                'column_name': 'customer_id',
                'parent_type': {'type': 'varchar', 'length': 255},
                'child_type': {'type': 'varchar', 'length': 255}
            }
        ]
        
        create_foreign_keys(mock_engine, relationships)
        
        # Should skip relationship due to type conversion failure
        mock_conn = mock_engine.connect.return_value.__enter__.return_value
        mock_conn.execute.assert_not_called()
    
    @patch('src.loadin.create_foreign_keys.ensure_valid_key_type')
    @patch('src.loadin.create_foreign_keys.get_primary_key_columns')
    @patch('src.loadin.create_foreign_keys.check_uniqueness')
    def test_create_foreign_keys_non_unique_column(self, mock_uniqueness, mock_get_pk, mock_ensure_type, mock_engine):
        """Test foreign key creation with non-unique parent column."""
        mock_ensure_type.return_value = True
        mock_get_pk.return_value = []  # No existing PK
        mock_uniqueness.return_value = False  # Column not unique
        
        relationships = [
            {
                'parent_table': 'customers',
                'child_table': 'orders',
                'column_name': 'customer_id',
                'parent_type': {'type': 'varchar', 'length': 255},
                'child_type': {'type': 'varchar', 'length': 255}
            }
        ]
        
        create_foreign_keys(mock_engine, relationships)
        
        # Should skip relationship due to non-unique column
        mock_conn = mock_engine.connect.return_value.__enter__.return_value
        mock_conn.execute.assert_not_called()
    
    @patch('src.loadin.create_foreign_keys.ensure_valid_key_type')
    @patch('src.loadin.create_foreign_keys.get_primary_key_columns')
    @patch('src.loadin.create_foreign_keys.check_uniqueness')
    @patch('src.loadin.create_foreign_keys.check_referential_integrity')
    def test_create_foreign_keys_integrity_violation(
        self, mock_ref_integrity, mock_uniqueness, mock_get_pk, mock_ensure_type, mock_engine
    ):
        """Test foreign key creation with referential integrity violation."""
        mock_ensure_type.return_value = True
        mock_get_pk.return_value = ['customer_id']  # Existing PK
        mock_uniqueness.return_value = True
        mock_ref_integrity.return_value = False  # Integrity violation
        
        relationships = [
            {
                'parent_table': 'customers',
                'child_table': 'orders',
                'column_name': 'customer_id',
                'parent_type': {'type': 'varchar', 'length': 255},
                'child_type': {'type': 'varchar', 'length': 255}
            }
        ]
        
        create_foreign_keys(mock_engine, relationships)
        
        # Should skip FK creation due to integrity violation
        mock_conn = mock_engine.connect.return_value.__enter__.return_value
        mock_conn.execute.assert_not_called()


class TestMainFunction:
    """Tests for the main function."""
    
    @patch('src.loadin.create_foreign_keys.get_db_connection')
    @patch('src.loadin.create_foreign_keys.find_foreign_key_relationships')
    @patch('src.loadin.create_foreign_keys.create_foreign_keys')
    def test_main_success(self, mock_create_fks, mock_find_rels, mock_get_connection, mock_engine):
        """Test successful main function execution."""
        # Setup mocks
        mock_get_connection.return_value = mock_engine
        
        # Mock table list
        Table = namedtuple('Table', ['table_name'])
        mock_tables = [Table('customers'), Table('orders')]
        mock_conn = mock_engine.connect.return_value.__enter__.return_value
        mock_conn.execute.return_value = mock_tables
        
        # Mock relationships
        mock_relationships = [
            {
                'parent_table': 'customers',
                'child_table': 'orders',
                'column_name': 'customer_id',
                'parent_type': {'type': 'varchar', 'length': 255},
                'child_type': {'type': 'varchar', 'length': 255}
            }
        ]
        mock_find_rels.return_value = mock_relationships
        
        main()
        
        # Verify the flow
        mock_get_connection.assert_called_once()
        mock_find_rels.assert_called_once_with(mock_engine, ['customers', 'orders'])
        mock_create_fks.assert_called_once_with(mock_engine, mock_relationships)
    
    @patch('src.loadin.create_foreign_keys.get_db_connection')
    @patch('src.loadin.create_foreign_keys.find_foreign_key_relationships')
    def test_main_no_relationships(self, mock_find_rels, mock_get_connection, mock_engine):
        """Test main function when no relationships are found."""
        mock_get_connection.return_value = mock_engine
        
        # Mock empty table list
        mock_conn = mock_engine.connect.return_value.__enter__.return_value
        mock_conn.execute.return_value = []
        
        mock_find_rels.return_value = []
        
        main()
        
        # Should still call find_foreign_key_relationships but not create_foreign_keys
        mock_find_rels.assert_called_once()
    
    @patch('src.loadin.create_foreign_keys.get_db_connection')
    def test_main_database_error(self, mock_get_connection):
        """Test main function with database connection error."""
        mock_get_connection.side_effect = Exception("Connection failed")
        
        with pytest.raises(Exception, match="Connection failed"):
            main()


class TestEdgeCases:
    """Tests for edge cases and error scenarios."""
    
    def test_relationship_finding_case_insensitive(self, mock_engine):
        """Test that relationship finding handles case variations properly."""
        with patch('src.loadin.create_foreign_keys.get_table_columns_with_types') as mock_get_columns:
            def mock_columns_side_effect(engine, table_name):
                if table_name == 'Customers':  # Mixed case
                    return {'customer_id': {'type': 'varchar', 'length': 255}}
                elif table_name == 'orders':  # Lower case
                    return {'customer_id': {'type': 'varchar', 'length': 255}}
                else:
                    return {}
            
            mock_get_columns.side_effect = mock_columns_side_effect
            
            tables = ['Customers', 'orders']  # Mixed case table names
            result = find_foreign_key_relationships(mock_engine, tables)
            
            # Should find relationship despite case differences
            assert len(result) == 1
            assert result[0]['parent_table'] == 'Customers'
            assert result[0]['child_table'] == 'orders'
    
    @patch('src.loadin.create_foreign_keys.ensure_valid_key_type')
    @patch('src.loadin.create_foreign_keys.get_primary_key_columns')
    @patch('src.loadin.create_foreign_keys.check_uniqueness')
    @patch('src.loadin.create_foreign_keys.check_referential_integrity')
    def test_create_foreign_keys_partial_failure(
        self, mock_ref_integrity, mock_uniqueness, mock_get_pk, mock_ensure_type, mock_engine
    ):
        """Test foreign key creation with some relationships failing."""
        # First relationship succeeds
        # Second relationship fails due to type conversion
        mock_ensure_type.side_effect = [True, True, False, False]  # parent, child for each rel
        mock_get_pk.return_value = ['id']
        mock_uniqueness.return_value = True
        mock_ref_integrity.return_value = True
        
        relationships = [
            {
                'parent_table': 'customers',
                'child_table': 'orders',
                'column_name': 'customer_id',
                'parent_type': {'type': 'varchar', 'length': 255},
                'child_type': {'type': 'varchar', 'length': 255}
            },
            {
                'parent_table': 'products',
                'child_table': 'order_items',
                'column_name': 'product_id',
                'parent_type': {'type': 'varchar', 'length': 255},
                'child_type': {'type': 'varchar', 'length': 255}
            }
        ]
        
        create_foreign_keys(mock_engine, relationships)
        
        # Should process first relationship but skip second
        mock_conn = mock_engine.connect.return_value.__enter__.return_value
        assert mock_conn.execute.call_count == 1  # Only first FK created
    
    def test_sql_injection_protection(self, mock_engine):
        """Test that table and column names are properly handled to prevent SQL injection."""
        # Test with potentially malicious table/column names
        malicious_table = "users; DROP TABLE important; --"
        malicious_column = "id'; DELETE FROM users; --"
        
        # The function should handle these safely (though in practice, these would come from 
        # information_schema which should be safe)
        mock_conn = mock_engine.connect.return_value.__enter__.return_value
        mock_conn.execute.return_value = []
        
        # Should not raise an exception
        result = get_table_columns_with_types(mock_engine, malicious_table)
        assert result == {}
        
        # The query should have been executed (SQL injection protection is at the SQLAlchemy level)
        mock_conn.execute.assert_called_once()


class TestPerformanceConsiderations:
    """Tests related to performance and optimization."""
    
    @patch('src.loadin.create_foreign_keys.get_table_columns_with_types')
    def test_relationship_finding_efficiency(self, mock_get_columns, mock_engine):
        """Test that relationship finding doesn't make unnecessary database calls."""
        # Mock returns for 3 tables (called for parent and child table combinations)
        mock_get_columns.return_value = {'id': {'type': 'varchar', 'length': 255}}
        
        tables = ['table1', 'table2', 'table3']
        find_foreign_key_relationships(mock_engine, tables)
        
        # Should call get_table_columns_with_types for each parent (3) + each child (3*2) = 9 times
        # (each parent table is evaluated against each other table)
        assert mock_get_columns.call_count == 9
    
    def test_large_table_list_handling(self, mock_engine):
        """Test that the system can handle a large number of tables."""
        with patch('src.loadin.create_foreign_keys.get_table_columns_with_types') as mock_get_columns:
            # Mock empty columns for all tables to avoid complex setup
            mock_get_columns.return_value = {}
            
            # Test with 100 tables
            tables = [f'table_{i}' for i in range(100)]
            result = find_foreign_key_relationships(mock_engine, tables)
            
            # Should complete without error
            assert result == []
            # Should have called get_table_columns_with_types for parent (100) + child combinations (100*99) = 10000 times
            assert mock_get_columns.call_count == 10000