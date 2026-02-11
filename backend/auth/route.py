from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from backend.auth.models import SignupRequest
from backend.auth.hash_utils import hash_password, verify_password
from backend.config.db import users_collection


router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBasic()

def authenticate_user(credentials: HTTPBasicCredentials = Depends(security)):
    user = users_collection.find_one({"username": credentials.username})
    role = user["role"] if user else None
    if user and verify_password(credentials.password, user["password"]):
        return user,role
    raise HTTPException(status_code=401, detail="Invalid credentials")


@router.post("/signup")
async def signup(signup_request: SignupRequest):
    existing_user = users_collection.find_one({"username": signup_request.username})
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    hashed_password = hash_password(signup_request.password)
    user_data = {
        "username": signup_request.username,
        "password": hashed_password,
        "email": signup_request.email,
        "role": signup_request.role,
    }
    users_collection.insert_one(user_data)
    return {"message": "User created successfully"}


@router.get("/login")
async def login(user_data: tuple = Depends(authenticate_user)):
    user, role = user_data
    return {"message": "Login successful", "username": user["username"], "role": role}