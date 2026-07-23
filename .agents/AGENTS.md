# Agent Behavioral Rules

## Rule Override: Use Real Data with Rate Limiting (Overrides original Rule 16)
The user has explicitly requested to stop mocking AI Gateway and external calls. 
- You MUST use real data and live API calls for testing moving forward.
- Because we are using the free tier of the AI models (Gemini), you MUST implement robust rate-limiting and sleep logic (`time.sleep()`) between API calls to prevent 429 Too Many Requests errors. Do not hit the API aggressively in loops.
