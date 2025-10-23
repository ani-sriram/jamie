#!/usr/bin/env python3
import json
import sqlite3
import sys
from pathlib import Path

def create_schema(conn):
    """Create the SQLite schema for recipes"""
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS recipes (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        ingredients_json TEXT NOT NULL,  -- Stored as JSON array of ingredient objects
        ingredients_text TEXT NOT NULL,  -- Denormalized text for fast searching
        instructions_json TEXT NOT NULL,  -- Stored as JSON array
        prep_time INTEGER NOT NULL,
        cook_time INTEGER NOT NULL,
        difficulty TEXT NOT NULL,
        servings INTEGER NOT NULL,
        tags TEXT,  -- Comma-separated tags
        search_text TEXT  -- Denormalized text for full-text search
    );
    
    -- Create indexes for common search patterns
    CREATE INDEX IF NOT EXISTS idx_ingredients_text ON recipes(ingredients_text);
    CREATE INDEX IF NOT EXISTS idx_difficulty ON recipes(difficulty);
    CREATE INDEX IF NOT EXISTS idx_prep_time ON recipes(prep_time);
    CREATE INDEX IF NOT EXISTS idx_tags ON recipes(tags);
    CREATE INDEX IF NOT EXISTS idx_search_text ON recipes(search_text);
    """)

def ingredients_to_text(ingredients):
    """Convert ingredients list to searchable text"""
    names = []
    for ing in ingredients:
        if isinstance(ing, dict):
            names.append(ing['name'].lower())
        else:
            names.append(str(ing).lower())
    return ','.join(names)

def create_search_text(recipe):
    """Create denormalized search text from recipe"""
    parts = [
        recipe['title'].lower(),
        ingredients_to_text(recipe['ingredients']),
        ','.join(str(tag).lower() for tag in recipe.get('tags', [])),
        recipe['difficulty'].lower()
    ]
    return ' '.join(filter(None, parts))

def migrate_recipes(json_path, db_path):
    """Migrate recipes from JSON to SQLite"""
    # Load JSON data
    with open(json_path, 'r') as f:
        recipes = json.load(f)
    
    # Create database connection
    conn = sqlite3.connect(db_path)
    
    try:
        # Create schema
        create_schema(conn)
        
        # Prepare insert statement
        insert_sql = """
        INSERT INTO recipes (
            id, title, ingredients_json, ingredients_text,
            instructions_json, prep_time, cook_time,
            difficulty, servings, tags, search_text
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        # Process each recipe
        for recipe in recipes:
            # Convert ingredients and instructions to JSON strings
            ingredients = recipe['ingredients']
            ingredients_json = json.dumps(ingredients)
            instructions_json = json.dumps(recipe['instructions'])
            
            # Create searchable ingredients text
            ingredient_names = []
            for ing in ingredients:
                if isinstance(ing, dict):
                    ingredient_names.append(ing['name'].lower())
                else:
                    ingredient_names.append(str(ing).lower())
            ingredients_text = ','.join(ingredient_names)
            
            # Get tags or empty list
            tags = recipe.get('tags', [])
            tags_str = ','.join(str(tag).lower() for tag in tags)
            
            # Create search text
            search_terms = [
                recipe['title'].lower(),
                ingredients_text,
                recipe['difficulty'].lower(),
                tags_str
            ]
            search_text = ' '.join(filter(None, search_terms))
            
            # Insert into database
            conn.execute(insert_sql, (
                recipe['id'],
                recipe['title'],
                ingredients_json,
                ingredients_text,
                instructions_json,
                recipe['prep_time'],
                recipe['cook_time'],
                recipe['difficulty'],
                recipe['servings'],
                tags_str,
                search_text
            ))
        
        # Commit changes
        conn.commit()
        print(f"Successfully migrated {len(recipes)} recipes to {db_path}")
        
    except Exception as e:
        print(f"Error during migration: {e}", file=sys.stderr)
        conn.rollback()
        raise
    finally:
        conn.close()

def main():
    # Set up paths
    src_dir = Path(__file__).resolve().parent.parent
    json_path = src_dir / 'data' / 'recipes.json'
    db_path = src_dir / 'data' / 'recipes.db'
    
    # Ensure source file exists
    if not json_path.exists():
        print(f"Error: {json_path} not found", file=sys.stderr)
        sys.exit(1)
    
    # Remove existing database if it exists
    if db_path.exists():
        print(f"Removing existing database: {db_path}")
        db_path.unlink()
    
    # Perform migration
    try:
        migrate_recipes(json_path, db_path)
    except Exception as e:
        print(f"Migration failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
