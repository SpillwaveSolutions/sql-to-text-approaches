#!/bin/bash

# Exit on any error
set -e

echo "Step 1: Running data import from SQLite to PostgreSQL..."
poetry run import-data
if [ $? -eq 0 ]; then
    echo "Data import completed successfully!"
else
    echo "Error: Data import failed!"
    exit 1
fi

echo -e "\nStep 2: Creating foreign key relationships..."
poetry run create-fks
if [ $? -eq 0 ]; then
    echo "Foreign key creation completed successfully!"
else
    echo "Error: Foreign key creation failed!"
    exit 1
fi

echo -e "\nAll steps completed successfully!"
