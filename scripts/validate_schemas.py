#!/usr/bin/env python3
import os
import sys
import json
import subprocess

# Ensure jsonschema is installed
try:
    import jsonschema
except ImportError:
    print("Installing 'jsonschema' package...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "jsonschema"])
    import jsonschema

# Define base paths
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARED_DIR = os.path.join(ROOT_DIR, "shared")
EXAMPLES_DIR = os.path.join(ROOT_DIR, "examples")

# Schema-to-example mappings
MAPPINGS = [
    {
        "schema": os.path.join(SHARED_DIR, "schemas", "config.schema.json"),
        "examples": [
            os.path.join(SHARED_DIR, "config", "examples"),
            os.path.join(EXAMPLES_DIR, "configs")
        ]
    },
    {
        "schema": os.path.join(SHARED_DIR, "schemas", "snapshot.schema.json"),
        "examples": [
            os.path.join(SHARED_DIR, "snapshot", "examples"),
            os.path.join(EXAMPLES_DIR, "snapshots")
        ]
    },
    {
        "schema": os.path.join(SHARED_DIR, "schemas", "metrics.schema.json"),
        "examples": [
            os.path.join(SHARED_DIR, "metrics", "examples")
        ]
    }
]

def validate_json_file(file_path, schema):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        jsonschema.validate(instance=data, schema=schema)
        print(f"  ✓ {os.path.basename(file_path)} is valid.")
        return True
    except json.JSONDecodeError as e:
        print(f"  ✗ {os.path.basename(file_path)}: Invalid JSON format: {e}")
        return False
    except jsonschema.exceptions.ValidationError as e:
        print(f"  ✗ {os.path.basename(file_path)}: Schema validation failed at path '{e.json_path}': {e.message}")
        return False

def main():
    overall_success = True
    schema_checked_count = 0
    file_checked_count = 0

    print("Starting JSON Schema Validation...")
    
    for mapping in MAPPINGS:
        schema_path = mapping["schema"]
        
        # If schema doesn't exist yet (e.g. initial setup phase), skip with warning
        if not os.path.exists(schema_path):
            print(f"Warning: Schema file not found: {os.path.relpath(schema_path, ROOT_DIR)} - Skipping.")
            continue
            
        print(f"Validating against: {os.path.relpath(schema_path, ROOT_DIR)}")
        schema_checked_count += 1
        
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)
            
        for example_dir in mapping["examples"]:
            if not os.path.exists(example_dir):
                continue
                
            for root, _, files in os.walk(example_dir):
                for file in files:
                    if file.endswith(".json"):
                        file_path = os.path.join(root, file)
                        file_checked_count += 1
                        success = validate_json_file(file_path, schema)
                        if not success:
                            overall_success = False

    print("\nValidation Summary:")
    print(f"  Schemas checked: {schema_checked_count}")
    print(f"  Files checked: {file_checked_count}")
    
    if not overall_success:
        print("\nResult: FAILURE (One or more files failed validation)")
        sys.exit(1)
    else:
        print("\nResult: SUCCESS")
        sys.exit(0)

if __name__ == "__main__":
    main()
