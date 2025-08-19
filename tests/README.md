# Test Suite Documentation

This directory contains comprehensive tests for the text-to-sql-approaches project, with a focus on the metadata processing modules.

## Running Tests

### Basic Test Execution
```bash
# Run all tests
poetry run pytest

# Run only unit tests
poetry run pytest tests/unit/

# Run only integration tests
poetry run pytest tests/integration/

# Run specific test file
poetry run pytest tests/unit/test_enrich_metadata.py

# Run specific test class or function
poetry run pytest tests/unit/test_enrich_metadata.py::TestGenerateColumnDescription
poetry run pytest tests/unit/test_enrich_metadata.py::TestGenerateColumnDescription::test_generate_column_description_success
```

### Test Markers
```bash
# Run only fast unit tests (skip integration and slow tests)
poetry run pytest -m "not integration and not slow"

# Run only integration tests
poetry run pytest -m integration

# Run tests that don't require external services
poetry run pytest -m "not openai and not real_db"
```

### Verbose Output
```bash
# Detailed output with test names and durations
poetry run pytest -v --durations=10

# Show stdout/stderr from tests
poetry run pytest -s

# Show local variables in tracebacks
poetry run pytest -l
```

## Environment Variables

### Required for All Tests
- `OPENAI_API_KEY`: Set to any value for unit tests (mocked), real key for integration tests

### Optional for Enhanced Testing
- `TEST_WITH_REAL_DB=1`: Enable tests requiring actual PostgreSQL connection
- `TEST_WITH_OPENAI=1`: Enable tests requiring actual OpenAI API calls

### Example Test Setup
```bash
export OPENAI_API_KEY="test-key-12345"
export TEST_WITH_REAL_DB=0
export TEST_WITH_OPENAI=0
poetry run pytest
```

## Test Fixtures

### Common Fixtures (conftest.py)
- `mock_engine`: Mock SQLAlchemy engine for unit tests
- `mock_openai_client`: Mock OpenAI client with standard responses
- `test_db_engine`: Real SQLite in-memory database for integration tests
- `sample_table_columns`: Sample database column metadata
- `sample_foreign_keys`: Sample foreign key relationship data
- `sample_relationships`: Sample FK relationships for testing

### Database Test Data
The integration tests use an in-memory SQLite database with:
- `test_customers` table (customer_id, customer_name, email, created_at)
- `test_orders` table (order_id, customer_id, order_date, total_amount)
- Foreign key relationship between orders.customer_id → customers.customer_id
- Sample data for testing referential integrity

## Test Coverage Areas

### Functional Testing
- ✅ Column metadata extraction and enrichment
- ✅ DDL generation for tables, constraints, indexes  
- ✅ Foreign key relationship detection and creation
- ✅ OpenAI API integration for description generation
- ✅ Database connection and query execution
- ✅ Error handling and edge cases

### Integration Testing
- ✅ End-to-end metadata enrichment workflow
- ✅ Cross-module data consistency
- ✅ Performance characteristics
- ✅ Concurrent access patterns
- ✅ Large schema handling

### Error Conditions
- ✅ Database connection failures
- ✅ OpenAI API errors and rate limiting
- ✅ Invalid table/column names
- ✅ Referential integrity violations
- ✅ Type conversion failures
- ✅ SQL syntax errors

## Best Practices for Test Development

### Writing Unit Tests
1. Use mocks for external dependencies (database, OpenAI API)
2. Test both success and failure paths
3. Include edge cases (empty results, malformed data)
4. Keep tests isolated and independent
5. Use descriptive test names that explain the scenario

### Writing Integration Tests
1. Use real database connections when possible
2. Clean up test data after each test
3. Test realistic data volumes
4. Verify end-to-end workflows
5. Include performance benchmarks

### Test Data Management
1. Use fixtures for reusable test data
2. Keep test data minimal but representative
3. Use factories for generating varied test data
4. Clean up after tests to avoid side effects

## Performance Testing

The test suite includes performance benchmarks for:
- Metadata extraction from databases with multiple tables
- Foreign key relationship detection algorithms
- Large schema processing
- Concurrent access patterns

Performance tests use timing assertions and should be adjusted based on expected system performance.

## Contributing

When adding new tests:
1. Follow the existing test structure and naming conventions
2. Add appropriate docstrings explaining what is being tested
3. Include both positive and negative test cases
4. Update this README if adding new test categories or fixtures
5. Ensure tests are deterministic and don't depend on external state

## CI/CD Integration

The test suite is designed to work in CI/CD environments:
- Uses environment variables for configuration
- Supports running subsets of tests based on available services
- Includes performance benchmarks with reasonable thresholds
- Provides clear pass/fail indicators for automated systems