# Note on Threading:
- When running FastAPI (via uvicorn/gunicorn), the server will keep the process running continuously to listen for HTTP requests.
- Threads created in analyze_multi.process() (default daemon=False) will continue running in parallel with the FastAPI main thread.
- FastAPI/uvicorn will NOT terminate the program until you stop the server (Ctrl+C or kill process).
- Therefore, there is no need to join() the video analysis threads as the program will not exit because the FastAPI event loop keeps the process alive.
- If running this script as a regular Python script (not a FastAPI server), the main thread ending will cause daemon=True child threads to stop as well.
- But with FastAPI, the server process is always alive, so the analysis threads continue to run in parallel."""