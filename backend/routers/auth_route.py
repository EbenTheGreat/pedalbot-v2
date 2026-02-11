# from fastapi import Depends
# from motor.motor_asyncio import AsyncIOMotorDatabase
# from backend.db.mongodb import get_database
# from backend.db.models import UserDocument, document_to_dict

# @app.post("/users")
# async def create_user(
#     email: str,
#     password: str,
#     db: AsyncIOMotorDatabase = Depends(get_database) 
# ):
#     user = UserDocument(
#         email=email,
#         hashed_password=hash_password(password)
#     )
    
#     result = await db.users.insert_one(document_to_dict(user))
#     return {"user_id": user.user_id}
