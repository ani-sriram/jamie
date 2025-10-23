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
        print("\nDebug info:")
        print(f"DB path: {tool.db_path}")
        
        # Check if DB exists
        db_path = Path(tool.db_path or str(src_path / "data" / "recipes.db"))
        print(f"DB exists: {db_path.exists()}")
        if db_path.exists():
            print(f"DB size: {db_path.stat().st_size} bytes")
            
        # Try to connect to DB
        try:
            from agent.tools.recipes import get_connection
            conn = get_connection(str(db_path))
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM recipes")
            count = cur.fetchone()[0]
            print(f"Recipe count in DB: {count}")
            conn.close()
        except Exception as db_e:
            print(f"Failed to query DB: {str(db_e)}")

if __name__ == "__main__":
    test_recipe_tool()