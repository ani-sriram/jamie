#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from google.cloud import firestore

def ingredients_to_text(ingredients):
    """Convert ingredients list to searchable text"""
    names = []
    for ing in ingredients:
        if isinstance(ing, dict):
            names.append(ing['name'].lower())
        else:
            names.append(str(ing).lower())
    return ','.join(names)

def migrate_recipes_to_firestore(json_path):
    """Migrate recipes from JSON to Firestore"""
    with open(json_path, 'r') as f:
        recipes = json.load(f)
    
    db = firestore.Client()
    collection = db.collection("recipes")
    
    batch = db.batch()
    batch_count = 0
    max_batch_size = 500
    
    try:
        for recipe in recipes:
            ingredients = recipe['ingredients']
            ingredient_names = []
            for ing in ingredients:
                if isinstance(ing, dict):
                    ingredient_names.append(ing['name'].lower())
                else:
                    ingredient_names.append(str(ing).lower())
            ingredients_text = ','.join(ingredient_names)
            
            tags = recipe.get('tags', [])
            tags_lower = [tag.lower() if isinstance(tag, str) else str(tag).lower() for tag in tags]
            
            doc_data = {
                'id': recipe['id'],
                'title': recipe['title'],
                'ingredients': ingredients,
                'ingredients_text': ingredients_text,
                'instructions': recipe['instructions'],
                'prep_time': recipe['prep_time'],
                'cook_time': recipe['cook_time'],
                'difficulty': recipe['difficulty'],
                'servings': recipe['servings'],
                'tags': tags_lower,
            }
            
            doc_ref = collection.document(recipe['id'])
            batch.set(doc_ref, doc_data)
            batch_count += 1
            
            if batch_count >= max_batch_size:
                batch.commit()
                print(f"Committed batch of {batch_count} recipes")
                batch = db.batch()
                batch_count = 0
        
        if batch_count > 0:
            batch.commit()
            print(f"Committed final batch of {batch_count} recipes")
        
        print(f"Successfully migrated {len(recipes)} recipes to Firestore")
        
    except Exception as e:
        print(f"Error during migration: {e}", file=sys.stderr)
        raise

def main():
    src_dir = Path(__file__).resolve().parent.parent
    json_path = src_dir / 'data' / 'recipes.json'
    
    if not json_path.exists():
        print(f"Error: {json_path} not found", file=sys.stderr)
        sys.exit(1)
    
    try:
        migrate_recipes_to_firestore(json_path)
    except Exception as e:
        print(f"Migration failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
