# from fastapi import FastAPI

# app = FastAPI()


# @app.get("/health")
# async def health_check():
#     return {"status": "healthy"}
# def main():
#     print("Hello from pedalbot-langgraph!")


# if __name__ == "__main__":
#     main()

# app/main.py
from fastapi import FastAPI
from backend.db.mongodb import init_db, close_db
from backend.config.config import settings

app = FastAPI()

@app.on_event("startup")
async def startup():
    await init_db(
        uri=settings.MONGODB_URI,
        db_name=settings.MONGODB_DB_NAME
    )

@app.on_event("shutdown")
async def shutdown():
    await close_db()