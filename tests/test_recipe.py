from agent.graph import JamieAgent

# agent = JamieAgent()
# response = agent.process_message(
#     user_id="test",
#     message="find me a chicken recipe"
# )
# print(response)

from agent.graph import JamieAgent

agent = JamieAgent()

# ============================================
# BASIC SEARCHES
# ============================================

# Single ingredient
# response = agent.process_message("test", "find me a chicken recipe")

"""
.search_recipes worked for chicken recipe

multi-ingredient -- is "or" not "and" --> need to fix 
"""

# Multiple ingredients  
# response = agent.process_message("test", "give me a recipe that uses mustard and thyme")
respone = agent.process_message("test", "give me a recipe with poop")
response = agent.process_message("test", "do you have context on previous messages? What ingredient did I just ask you about?")
print(response)
# Specific dish by name
# response = agent.process_message("test", "how do I make carbonara?")

# ============================================
# FILTERS
# ============================================

# Difficulty filter
# response = agent.process_message("test", "find me a easy/medium difficulty recipe")

# Time constraint
# response = agent.process_message("test", "I need something quick, under 30 minutes")

# Tag/cuisine search
# response = agent.process_message("test", "I want to cook something italian")

# Servings
# response = agent.process_message("test", "I need a recipe that feeds 6 hmm... around 6 people")

# ============================================
# EXCLUSIONS & RESTRICTIONS
# ============================================

# Exclude ingredient
# response = agent.process_message("test", "find me recipes without peanut. I have an allergy")

# Dietary restriction
# response = agent.process_message("test", "find me a vegetarian dinner recipe")

# ============================================
# COMBINED FILTERS
# ============================================

# Multiple constraints
# response = agent.process_message("test", "easy chicken recipe under 45 minutes")

# Complex request
# response = agent.process_message("test", "I want a quick italian dish that's vegetarian")

# ============================================
# EDGE CASES
# ============================================

# Ingredient that probably doesn't exist
# response = agent.process_message("test", "find me a recipe with dragon fruit")

# Very vague
# response = agent.process_message("test", "I'm hungry")

# Ambiguous (could be recipe or restaurant)
# response = agent.process_message("test", "I want pizza")

print(response)