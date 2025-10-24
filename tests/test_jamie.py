import pytest
import json
import time
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# Add src to Python path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from agent.graph import JamieAgent
from agent.schemas import ConversationMessage, MessageRole


class TestJamieAgent:
    """Comprehensive tests for the Jamie agent with multi-turn conversations"""

    @pytest.fixture
    def agent(self):
        """Create a Jamie agent instance for testing"""
        return JamieAgent()

    @pytest.fixture
    def test_logger(self):
        """Set up logging for test results"""
        # Create logs directory if it doesn't exist
        log_dir = Path(__file__).parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)

        # Create logger
        logger = logging.getLogger("jamie_tests")
        logger.setLevel(logging.INFO)

        # Create file handler with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"jamie_test_results_{timestamp}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)

        # Add handler to logger
        logger.addHandler(file_handler)

        return logger

    def run_conversation(
        self,
        agent: JamieAgent,
        conversation: List[str],
        test_name: str,
        logger: logging.Logger,
    ) -> Dict[str, Any]:
        """Run a multi-turn conversation and measure performance"""
        logger.info(f"\n{'='*60}")
        logger.info(f"TEST: {test_name}")
        logger.info(f"{'='*60}")

        start_time = time.time()
        conversation_history = []
        responses = []
        turn_times = []

        for i, user_message in enumerate(conversation):
            turn_start = time.time()

            logger.info(f"\n--- Turn {i+1} ---")
            logger.info(f"User: {user_message}")

            # Process message with agent
            response = agent.process_message(
                user_id="test_user",
                message=user_message,
                session_id="test_session",
                conversation_history=conversation_history,
            )

            turn_time = time.time() - turn_start
            turn_times.append(turn_time)

            logger.info(f"Agent: {response}")
            logger.info(f"Turn {i+1} time: {turn_time:.2f}s")

            # Store conversation
            conversation_history.append(
                ConversationMessage(
                    session_id="test_session",
                    user_id="test_user",
                    role=MessageRole.USER,
                    content=user_message,
                    timestamp=datetime.utcnow().isoformat() + "Z",
                )
            )

            conversation_history.append(
                ConversationMessage(
                    session_id="test_session",
                    user_id="test_user",
                    role=MessageRole.ASSISTANT,
                    content=response,
                    timestamp=datetime.utcnow().isoformat() + "Z",
                )
            )

            responses.append(response)

        total_time = time.time() - start_time

        result = {
            "test_name": test_name,
            "total_time": total_time,
            "turn_times": turn_times,
            "avg_turn_time": sum(turn_times) / len(turn_times),
            "responses": responses,
            "conversation": conversation,
        }

        logger.info(f"\n--- Test Summary ---")
        logger.info(f"Total time: {total_time:.2f}s")
        logger.info(f"Average turn time: {result['avg_turn_time']:.2f}s")
        logger.info(f"Number of turns: {len(conversation)}")

        return result

    # RESTAURANT TESTS
    def test_restaurant_basic_search(self, agent, test_logger):
        """Basic restaurant search test"""
        conversation = [
            "Find ice cream near me",
            "I'm in downtown San Francisco",
            "Which of these is open after 11 PM?",
        ]
        return self.run_conversation(
            agent, conversation, "Restaurant Basic Search", test_logger
        )

    def test_restaurant_detailed_inquiry(self, agent, test_logger):
        """Detailed restaurant inquiry test"""
        conversation = [
            "I want Italian food in Manhattan",
            "What are the prices like at the first one?",
            "Does it have outdoor seating?",
            "What are the hours for the second restaurant?",
        ]
        return self.run_conversation(
            agent, conversation, "Restaurant Detailed Inquiry", test_logger
        )

    def test_restaurant_picky_customer(self, agent, test_logger):
        """Picky customer scenario"""
        conversation = [
            "Find me a restaurant",
            "I'm in Los Angeles",
            "I want something healthy and organic",
            "No, that's too expensive",
            "Actually, I changed my mind, I want Mexican food",
            "But it has to be vegetarian",
            "And open past 9 PM",
        ]
        return self.run_conversation(
            agent, conversation, "Restaurant Picky Customer", test_logger
        )

    def test_restaurant_location_confusion(self, agent, test_logger):
        """Customer with location confusion"""
        conversation = [
            "Find sushi restaurants",
            "I think I'm in Seattle near the Space Needle. Not sure which neighborhood this is",
            "No wait, I'm actually closer to South Lake Union",
            "Which one won't be busy at 2pm on a Tuesday?",
        ]
        return self.run_conversation(
            agent, conversation, "Restaurant Location Confusion", test_logger
        )

    def test_restaurant_specific_cuisine(self, agent, test_logger):
        """Specific cuisine search"""
        conversation = [
            "I want authentic Thai food in Chicago",
            "Which one is closest to the Loop?",
            "Do any of them have delivery?",
            "What's the spice level like at the first one?",
        ]
        return self.run_conversation(
            agent, conversation, "Restaurant Specific Cuisine", test_logger
        )

    def test_restaurant_price_sensitive(self, agent, test_logger):
        """Price-sensitive customer"""
        conversation = [
            "Find cheap restaurants near me",
            "I'm in Austin, Texas",
            "Under $20 per person",
            "Is there anything under $10 per person?",
            "What about food trucks?",
            "Which one do you think has the best value in terms of portion size?",
        ]
        return self.run_conversation(
            agent, conversation, "Restaurant Price Sensitive", test_logger
        )

    def test_restaurant_group_dining(self, agent, test_logger):
        """Group dining scenario"""
        conversation = [
            "I need a restaurant for 8 people in Miami",
            "We want something nice but not too fancy",
            "Does the second one take reservations?",
            "Is there parking available nearby for free?",
        ]
        return self.run_conversation(
            agent, conversation, "Restaurant Group Dining", test_logger
        )

    def test_restaurant_dietary_restrictions(self, agent, test_logger):
        """Customer with dietary restrictions"""
        conversation = [
            "Find restaurants in Denver",
            "I'm gluten-free and vegan",
            "Do any of them have good options for me?",
            "What about the second one's menu?",
            "Can you check if they have gluten-free bread?",
        ]
        return self.run_conversation(
            agent, conversation, "Restaurant Dietary Restrictions", test_logger
        )

    def test_restaurant_annoying_customer(self, agent, test_logger):
        """Annoying customer scenario"""
        conversation = [
            "I want food",
            "Just find me something good",
            "Fine, just find me pizza",
            "I want artisanal pizza",
            "Actually, forget pizza, I want burgers",
            "Do they have truffle fries",
            "And I cant forget my craft beer",
            "In a trendy neighborhood",
            "Do they have good music and outdoor seating?",
            "But it has to be underground. Like no higher than 4 stars",
            "And whats the best dessert option in that area?",
        ]
        return self.run_conversation(
            agent, conversation, "Restaurant Annoying Customer (10 turns)", test_logger
        )

    def test_restaurant_emergency_food(self, agent, test_logger):
        """Emergency food situation"""
        conversation = [
            "I'm in Boston Logan Airport and I'm starving and need food NOW",
            "I don't care what kind, just something fast",
            "Which one can I get to the quickest from the airport and is open now, but not airport food because thats too expensive",
        ]
        return self.run_conversation(
            agent, conversation, "Restaurant Emergency Food", test_logger
        )

    # RECIPE TESTS
    def test_recipe_basic_search(self, agent, test_logger):
        """Basic recipe search test"""
        conversation = [
            "I want to make pasta",
            "What ingredients do I need for the first recipe?",
            "How long does it take to cook?",
        ]
        return self.run_conversation(
            agent, conversation, "Recipe Basic Search", test_logger
        )

    def test_recipe_dietary_restrictions(self, agent, test_logger):
        """Recipe search with dietary restrictions"""
        conversation = [
            "I want to make a pizza",
            "What can I substitute for flour since I want it gluten free",
            "How many servings does it make?",
        ]
        return self.run_conversation(
            agent, conversation, "Recipe Dietary Restrictions", test_logger
        )

    def test_recipe_beginner_cook(self, agent, test_logger):
        """Beginner cook scenario"""
        conversation = [
            "I'm new to cooking, what's easy to make?",
            "I have chicken and rice",
            "Is that recipe really easy?",
            "Can you give me step-by-step instructions?",
            "I accidentally added too much salt after step 3 how can i save the dish?"
        ]
        return self.run_conversation(
            agent, conversation, "Recipe Beginner Cook", test_logger
        )

    def test_recipe_ingredient_substitution(self, agent, test_logger):
        """Ingredient substitution scenario"""
        conversation = [
            "Hi my name is Dave and I want to make chocolate cake",
            "I don't have eggs, what can I use instead?",
            "What about the flour, can I use whole wheat?",
            "I also don't have butter, any alternatives?",
        ]
        return self.run_conversation(
            agent, conversation, "Recipe Ingredient Substitution", test_logger
        )

    def test_recipe_time_constraints(self, agent, test_logger):
        """Time-constrained cooking"""
        conversation = [
            "I need something I can make in 30 minutes",
            "I have ground beef and vegetables",
            "Which recipe is fastest?",
            "Can I skip any steps to make it quicker?",
        ]
        return self.run_conversation(
            agent, conversation, "Recipe Time Constraints", test_logger
        )

    def test_user_isolation_specific(self, agent, test_logger):
        """Specific cuisine recipe search"""
        conversation = [
            "My name is John. What ingredients was Dave missing for his chocolate cake?",
        ]
        return self.run_conversation(
            agent, conversation, "Recipe User Isolation", test_logger
        )
    
    def test_user_memory(self, agent, test_logger):
        """User memory across sessions"""
        conversation = [
            "Hi, I'm Sarah. Last time I cooked with you, I made a vegan lasagna. Can you remind me what ingredients I used so I can buy more?",
        ]
        return self.run_conversation(
            agent, conversation, "Recipe User Memory", test_logger
        )

    def test_recipe_health_conscious(self, agent, test_logger):
        """Health-conscious cooking"""
        conversation = [
            "Find me healthy recipes",
            "I want low-carb options",
            "What's the calorie count for the first recipe?",
            "Can I make it even healthier?",
        ]
        return self.run_conversation(
            agent, conversation, "Recipe Health Conscious", test_logger
        )

    def test_recipe_equipment_limited(self, agent, test_logger):
        """Limited equipment scenario"""
        conversation = [
            "I want to cook dinner for two tonight.",
            "Maybe some kind of creamy pasta, but it can't be over 600 calories per serving.",
            "Actually one of my guests is lactose intolerant, can we swap out the cream?",
            "If I use oat milk instead, will the calories change much?",
            "Wait, I also need it to be vegetarian—can I replace the chicken you suggested?",
            "Could I add mushrooms instead, or would that mess with the texture?",
            "Can we keep it around 30 minutes of prep?",
            "I just remembered I only have whole wheat pasta—does that change the timing or calories?",
            "If this is getting complicated, maybe a stir-fry would be better. What would you recommend?",
            "Do I need to buy anything special or can I use pantry staples?",
            "Oh, and I'd like a side salad—any low-calorie dressing ideas?",
            "Can you summarize the recipe with calorie estimates for each part so I don't mess up?",
        ]
        return self.run_conversation(
            agent, conversation, "Recipe Equipment Limited", test_logger
        )

    def test_recipe_annoying_cook(self, agent, test_logger):
        """Annoying cook scenario"""
        conversation = [
            "I'm trying to cook dinner this weekend, maybe something cozy like lasagna.",
            "Actually, that sounds heavy—do you have a lighter option under 500 calories per serving?",
            "Can we make it gluten-free without ruining the texture?",
            "If I swap regular pasta for zucchini noodles, how does that change the calories?",
            "I changed my mind, let's do salmon instead—what's a good recipe?",
            "But my friend doesn't eat fish; can we keep the same flavors with tofu?",
            "Do I need any special equipment, or will a cast iron and oven be enough?",
            "Could we add a creamy sauce while keeping it lactose-free?",
            "Would coconut milk work, and how many calories would that add?",
            "Maybe add a grain—could quinoa fit without bumping the calories too much?",
            "Actually, can we turn this into meal prep for lunches too?",
            "Please list the substitutions and updated calorie count so I don't get lost.",
        ]
        return self.run_conversation(
            agent, conversation, "Recipe Annoying Cook (12 turns)", test_logger
        )

    def test_recipe_meal_planning(self, agent, test_logger):
        """Meal planning scenario"""
        conversation = [
            "I need to plan meals for the week",
            "I want variety but not too complicated",
            "Can you suggest a few different cuisines?",
            "What about meal prep options?",
            "Which recipes can I make ahead?",
        ]
        return self.run_conversation(
            agent, conversation, "Recipe Meal Planning", test_logger
        )

    def run_all_tests(self, agent, test_logger):
        """Run all tests and generate summary report"""
        test_logger.info(f"\n{'='*80}")
        test_logger.info(f"STARTING COMPREHENSIVE JAMIE AGENT TEST SUITE")
        test_logger.info(f"Timestamp: {datetime.now().isoformat()}")
        test_logger.info(f"{'='*80}")

        # Restaurant tests
        restaurant_tests = [
            self.test_restaurant_basic_search,
            self.test_restaurant_detailed_inquiry,
            self.test_restaurant_picky_customer,
            self.test_restaurant_location_confusion,
            self.test_restaurant_specific_cuisine,
            self.test_restaurant_price_sensitive,
            self.test_restaurant_group_dining,
            self.test_restaurant_dietary_restrictions,
            self.test_restaurant_annoying_customer,
            self.test_restaurant_emergency_food,
        ]

        # Recipe tests
        recipe_tests = [
            self.test_recipe_basic_search,
            self.test_recipe_dietary_restrictions,
            self.test_recipe_beginner_cook,
            self.test_recipe_ingredient_substitution,
            self.test_recipe_time_constraints,
            self.test_recipe_cuisine_specific,
            self.test_recipe_health_conscious,
            self.test_recipe_equipment_limited,
            self.test_recipe_annoying_cook,
            self.test_recipe_meal_planning,
        ]

        all_results = []

        # Run restaurant tests
        test_logger.info(f"\n{'='*40} RESTAURANT TESTS {'='*40}")
        for test_func in restaurant_tests:
            try:
                result = test_func(agent, test_logger)
                all_results.append(result)
            except Exception as e:
                test_logger.error(f"Restaurant test {test_func.__name__} failed: {e}")

        # Run recipe tests
        test_logger.info(f"\n{'='*40} RECIPE TESTS {'='*40}")
        for test_func in recipe_tests:
            try:
                result = test_func(agent, test_logger)
                all_results.append(result)
            except Exception as e:
                test_logger.error(f"Recipe test {test_func.__name__} failed: {e}")

        # Generate summary
        self.generate_summary_report(all_results, test_logger)

        return all_results

    def generate_summary_report(
        self, results: List[Dict[str, Any]], test_logger: logging.Logger
    ):
        """Generate a summary report of all test results"""
        test_logger.info(f"\n{'='*80}")
        test_logger.info(f"TEST SUMMARY REPORT")
        test_logger.info(f"{'='*80}")

        total_tests = len(results)
        total_time = sum(r["total_time"] for r in results)
        avg_test_time = total_time / total_tests if total_tests > 0 else 0

        # Calculate turn statistics
        all_turn_times = []
        for result in results:
            all_turn_times.extend(result["turn_times"])

        avg_turn_time = (
            sum(all_turn_times) / len(all_turn_times) if all_turn_times else 0
        )
        max_turn_time = max(all_turn_times) if all_turn_times else 0
        min_turn_time = min(all_turn_times) if all_turn_times else 0

        test_logger.info(f"Total tests run: {total_tests}")
        test_logger.info(f"Total execution time: {total_time:.2f}s")
        test_logger.info(f"Average test time: {avg_test_time:.2f}s")
        test_logger.info(f"Average turn time: {avg_turn_time:.2f}s")
        test_logger.info(f"Fastest turn: {min_turn_time:.2f}s")
        test_logger.info(f"Slowest turn: {max_turn_time:.2f}s")

        # Test-specific statistics
        restaurant_tests = [r for r in results if "Restaurant" in r["test_name"]]
        recipe_tests = [r for r in results if "Recipe" in r["test_name"]]

        test_logger.info(f"\nRestaurant tests: {len(restaurant_tests)}")
        if restaurant_tests:
            restaurant_avg = sum(r["total_time"] for r in restaurant_tests) / len(
                restaurant_tests
            )
            test_logger.info(f"Average restaurant test time: {restaurant_avg:.2f}s")

        test_logger.info(f"\nRecipe tests: {len(recipe_tests)}")
        if recipe_tests:
            recipe_avg = sum(r["total_time"] for r in recipe_tests) / len(recipe_tests)
            test_logger.info(f"Average recipe test time: {recipe_avg:.2f}s")

        # Individual test results
        test_logger.info(f"\n{'='*40} INDIVIDUAL TEST RESULTS {'='*40}")
        for result in results:
            test_logger.info(
                f"{result['test_name']}: {result['total_time']:.2f}s "
                f"({len(result['conversation'])} turns, "
                f"avg {result['avg_turn_time']:.2f}s/turn)"
            )


if __name__ == "__main__":
    # Run a single test for demonstration
    import sys
    from pathlib import Path

    # Add src to path
    src_path = Path(__file__).parent.parent / "src"
    sys.path.insert(0, str(src_path))

    # Create test instance
    test_instance = TestJamieAgent()
    agent = test_instance.agent()
    logger = test_instance.test_logger()

    # Run all tests
    results = test_instance.run_all_tests(agent, logger)

    print(f"\nTest completed! Check the logs directory for detailed results.")
    print(f"Total tests run: {len(results)}")
