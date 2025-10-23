#!/usr/bin/env python3
"""
Example usage of Jamie Food Agent
"""

import requests
import json

BASE_URL = "http://localhost:8000"
TIMEOUT = (5, 45)  # (connect timeout, read timeout)

def test_jamie_agent():
    user_id = "demo_user"
    
    # Test messages
    # test_messages = [
    #     "I'm craving Italian food",
    #     "What can I cook with chicken and pasta?",
    #     "I want to order pizza from Mario's",
    #     "Show me some healthy recipes",
    #     "Find me a good sushi place"
    # ]
    with open("sample_messages.txt") as f:
        test_messages = [line.strip() for line in f if line.strip()][:5]
    
    print("Testing Jamie Food Agent")
    print("=" * 50)
    
    for i, message in enumerate(test_messages, 1):
        print(f"\n{i}. User: {message}")
        
        try:
            response = requests.post(
                f"{BASE_URL}/chat/{user_id}",
                json={"message": message},
                timeout=TIMEOUT,
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"   Jamie: {data['response']}")

                # Evaluate the response using /evals
                try:
                    eval_req = {
                        "user_input": message,
                        "llm_response": data["response"],
                    }
                    eval_res = requests.post(
                        f"{BASE_URL}/evals",
                        json=eval_req,
                        timeout=TIMEOUT,
                    )
                    if eval_res.status_code == 200:
                        eval_data = eval_res.json()
                        print(f"   Eval: score={eval_data['score']} reason={eval_data['reason']}")
                    else:
                        print(f"   Eval error: {eval_res.status_code} - {eval_res.text}")
                except Exception as ee:
                    print(f"   Eval call failed: {ee}")
            else:
                print(f"   Error: {response.status_code} - {response.text}")
                
        except requests.exceptions.ConnectionError:
            print("   Error: Could not connect to server. Make sure Jamie is running!")
            break
        except Exception as e:
            print(f"   Error: {e}")
    
    # Check health
    print(f"\nHealth Check:")
    try:
        health = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)
        if health.status_code == 200:
            print(f"   Status: {health.json()}")
    except:
        print("   Could not check health status")

if __name__ == "__main__":
    test_jamie_agent()
