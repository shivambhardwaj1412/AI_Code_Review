from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"status": "AI Code Reviewer - Day 2 skeleton running!"}

# uvicorn main:app --reload(To see code running)
# Biswajit will complete the /webhook endpoint