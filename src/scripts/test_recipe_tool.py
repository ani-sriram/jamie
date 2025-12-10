#!/usr/bin/env python3
import sys
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).resolve().parent.parent
sys.path.append(str(src_path))

from agent.tools.recipes import RecipeTool
from agent.schemas import Recipe

def test_recipe_tool():
    print("\n=== Testing RecipeTool ===")
    
    # Initialize tool
    tool = RecipeTool()
    
    try:
        print("\nTesting find_recipes:")
        results = tool.find_recipes(["chicken"])
        print(f"Found {len(results)} recipes with chicken")
        for r in results:
            print(f"- {r.title}")
        
        print("\nTesting search_by_title:")
        results = tool.search_by_title("carbonara")
        print(f"Found {len(results)} recipes matching 'carbonara'")
        for r in results:
            print(f"- {r.title}")
        
        print("\nTesting get_recipe_by_id:")
        recipe = tool.get_recipe_by_id("recipe_001")
        if recipe:
            print(f"Found recipe: {recipe.title}")
            print(f"Ingredients: {[ing.name for ing in recipe.ingredients]}")
            print(f"Tags: {recipe.tags}")
        else:
            print("Recipe not found")
        
        print("\nTesting search_recipes with filters:")
        results = tool.search_recipes(
            ingredients=[{"name": "chicken"}],
            difficulty="easy",
            max_total_time=45
        )
        print(f"Found {len(results)} easy chicken recipes under 45 minutes")
        for r in results:
            print(f"- {r.title} ({r.prep_time + r.cook_time} mins)")
            
    except Exception as e:
        import traceback
        print(f"\n❌ Error occurred: {str(e)}")
        print("\nFull traceback:")
        print(traceback.format_exc())
        print("\nNote: This test requires Firestore to be set up and populated with recipes.")
        print("Run: python src/scripts/migrate_db.py to populate Firestore with recipes.")

if __name__ == "__main__":
    test_recipe_tool()