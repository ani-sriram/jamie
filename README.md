# Jamie - LLM-Powered Food Recommendation Agent

Jamie is a conversational assistant that helps users decide what to eat by suggesting restaurant meals, delivery options, or home-cooked recipes.

## Features

- Multi-turn conversational agent using LangGraph
- Restaurant meal recommendations
- Home-cooked recipe suggestions
- Mock ordering system
- Per-user containerized isolation

## Quick Start

1. Install dependencies:
```bash
uv sync
uv pip install -e .
```

2. Set up environment variables:
```bash
# Copy the example environment file
cp env.example .env

# Edit .env with your actual values
export GCP_PROJECT_ID=XXXXX
export GEMINI_API_KEY=XXXXX
export PLACES_API_KEY=XXXXX
```

3. Run the backend application:
```bash
uv run src/main.py
```
4. Start the front end:
    1. Navigate to the frontend directory:
    ```bash
    cd frontend
    ```

    2. Install dependencies:
    ```bash
    npm install
    ```

    3. Start the development server:
    ```bash
    npm start
## API Endpoints

- `POST /chat/{user_id}` - Send messages to Jamie
- `GET /health` - Health check