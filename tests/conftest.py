"""Pytest configuration and shared fixtures."""
import os
import pytest
from unittest.mock import Mock, MagicMock
import tempfile
import sqlite3
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# Mock database fixture
@pytest.fixture
def mock_engine():
    """Create a mock SQLAlchemy engine for unit tests."""
    engine = Mock(spec=Engine)
    connection = Mock()
    
    # Create a mock context manager for the connection
    context_manager = Mock()
    context_manager.__enter__ = Mock(return_value=connection)
    context_manager.__exit__ = Mock(return_value=None)
    
    engine.connect.return_value = context_manager
    return engine

@pytest.fixture
def mock_openai_client():
    """Create a mock OpenAI client."""
    client = Mock()
    response = Mock()
    response.choices = [Mock()]
    response.choices[0].message.content = "Mock column description for testing purposes."
    client.chat.completions.create.return_value = response
    return client

@pytest.fixture
def test_db_engine():
    """Create a real SQLite engine for integration tests."""
    # Create in-memory SQLite database for testing
    engine = create_engine("sqlite:///:memory:")
    
    # Create test tables
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE test_customers (
                customer_id TEXT PRIMARY KEY,
                customer_name TEXT NOT NULL,
                email TEXT,
                created_at TIMESTAMP
            )
        """))
        
        conn.execute(text("""
            CREATE TABLE test_orders (
                order_id TEXT PRIMARY KEY,
                customer_id TEXT,
                order_date TIMESTAMP,
                total_amount DECIMAL(10,2),
                FOREIGN KEY (customer_id) REFERENCES test_customers(customer_id)
            )
        """))
        
        # Insert test data
        conn.execute(text("""
            INSERT INTO test_customers (customer_id, customer_name, email, created_at)
            VALUES 
                ('cust1', 'John Doe', 'john@example.com', '2023-01-01'),
                ('cust2', 'Jane Smith', 'jane@example.com', '2023-01-02')
        """))
        
        conn.execute(text("""
            INSERT INTO test_orders (order_id, customer_id, order_date, total_amount)
            VALUES 
                ('ord1', 'cust1', '2023-01-15', 99.99),
                ('ord2', 'cust1', '2023-01-20', 149.50),
                ('ord3', 'cust2', '2023-01-18', 75.25)
        """))
        
        conn.commit()
    
    return engine

@pytest.fixture
def sample_table_columns():
    """Sample table column data for testing."""
    return [
        ('customer_id', 'character varying', False, 'Unique identifier for customer'),
        ('customer_name', 'character varying', False, ''),
        ('email', 'character varying', True, 'Customer email address'),
        ('created_at', 'timestamp without time zone', True, '')
    ]

@pytest.fixture
def sample_foreign_keys():
    """Sample foreign key relationships for testing."""
    return [
        {
            "fk_name": "fk_orders_customer",
            "parent_table": "orders", 
            "parent_column": "customer_id",
            "referenced_table": "customers",
            "referenced_column": "customer_id"
        }
    ]

@pytest.fixture
def sample_relationships():
    """Sample foreign key relationships for create_foreign_keys tests."""
    return [
        {
            'parent_table': 'customers',
            'child_table': 'orders', 
            'column_name': 'customer_id',
            'parent_type': {'type': 'character varying', 'length': 255},
            'child_type': {'type': 'character varying', 'length': 255}
        },
        {
            'parent_table': 'products',
            'child_table': 'order_items',
            'column_name': 'product_id', 
            'parent_type': {'type': 'character varying', 'length': 255},
            'child_type': {'type': 'character varying', 'length': 255}
        }
    ]

# Set up environment variables for testing
@pytest.fixture(autouse=True)
def setup_test_env():
    """Set up test environment variables."""
    original_openai_key = os.environ.get('OPENAI_API_KEY')
    os.environ['OPENAI_API_KEY'] = 'test-key-12345'
    
    yield
    
    # Cleanup
    if original_openai_key is not None:
        os.environ['OPENAI_API_KEY'] = original_openai_key
    elif 'OPENAI_API_KEY' in os.environ:
        del os.environ['OPENAI_API_KEY']