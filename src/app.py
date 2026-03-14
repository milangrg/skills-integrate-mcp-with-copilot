"""
High School Management System API

A simple FastAPI app for students to view and sign up for extracurricular activities.
Added role-based auth + per-user dashboards.
"""

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional
import os
from pathlib import Path
import uuid

app = FastAPI(
    title="Mergington High School API",
    description="API for viewing and signing up for extracurricular activities",
)

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent, "static")), name="static")

# In-memory (demo) user store with roles
users = {
    "admin@mergington.edu": {"password": "adminpass", "role": "administrator"},
    "faculty@mergington.edu": {"password": "facultypass", "role": "faculty"},
    "student@mergington.edu": {"password": "studentpass", "role": "student"},
}

# In-memory token store (session-like)
api_tokens: dict[str, dict] = {}

# In-memory activity database
activities = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"],
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"],
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"],
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"],
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"],
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"],
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"],
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"],
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"],
    },
}


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class ParticipantAction(BaseModel):
    email: str


def get_current_user(x_api_token: Optional[str] = Header(None, alias="X-API-Token")):
    if not x_api_token:
        raise HTTPException(status_code=401, detail="X-API-Token header required")
    if x_api_token not in api_tokens:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return api_tokens[x_api_token]


def require_role(required: str):
    def role_checker(user: dict = Depends(get_current_user)):
        if user["role"] != required:
            raise HTTPException(status_code=403, detail="Insufficient role privileges")
        return user

    return role_checker


@app.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    user = users.get(payload.email)
    if not user or user["password"] != payload.password:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = str(uuid.uuid4())
    api_tokens[token] = {"email": payload.email, "role": user["role"]}

    return LoginResponse(access_token=token, role=user["role"])


@app.post("/logout")
def logout(user: dict = Depends(get_current_user)):
    token_to_remove = None
    for token, info in list(api_tokens.items()):
        if info["email"] == user["email"]:
            token_to_remove = token
            break
    if token_to_remove:
        del api_tokens[token_to_remove]
    return {"message": "Logged out"}


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/dashboard")
def dashboard(user: dict = Depends(get_current_user)):
    role = user["role"]
    base = {"email": user["email"], "role": role}

    if role == "administrator":
        base["capabilities"] = ["read_activities", "create_activity", "enroll_any", "delete_any"]
    elif role == "faculty":
        base["capabilities"] = ["read_activities", "enroll_any", "view_students"]
    else:
        base["capabilities"] = ["read_activities", "enroll_self", "view_self"]

    return base


@app.get("/activities")
def get_activities(user: dict = Depends(get_current_user)):
    return activities


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, action: ParticipantAction, user: dict = Depends(get_current_user)):
    if user["role"] != "student":
        raise HTTPException(status_code=403, detail="Only students can sign up for activities")

    # Confirm the student is signing themselves up
    if action.email != user["email"]:
        raise HTTPException(status_code=403, detail="Students can only sign themselves up")

    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    activity = activities[activity_name]
    if action.email in activity["participants"]:
        raise HTTPException(status_code=400, detail="Student is already signed up")

    if len(activity["participants"]) >= activity["max_participants"]:
        raise HTTPException(status_code=400, detail="Activity is full")

    activity["participants"].append(action.email)
    return {"message": f"Signed up {action.email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, action: ParticipantAction, user: dict = Depends(get_current_user)):
    if user["role"] != "student":
        raise HTTPException(status_code=403, detail="Only students can unregister from activities")

    if action.email != user["email"]:
        raise HTTPException(status_code=403, detail="Students can only unregister themselves")

    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    activity = activities[activity_name]
    if action.email not in activity["participants"]:
        raise HTTPException(status_code=400, detail="Student is not signed up for this activity")

    activity["participants"].remove(action.email)
    return {"message": f"Unregistered {action.email} from {activity_name}"}


@app.post("/activities/{activity_name}/admin-remove")
def admin_remove_participant(activity_name: str, action: ParticipantAction, user: dict = Depends(require_role("administrator"))):
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    activity = activities[activity_name]
    if action.email not in activity["participants"]:
        raise HTTPException(status_code=400, detail="Student is not signed up for this activity")

    activity["participants"].remove(action.email)
    return {"message": f"Administrator removed {action.email} from {activity_name}"}
