from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.identity import EMPLOYEES, DEMO_PASSWORD, issue_employee_token, current_employee

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/users")
def demo_users():
    """The sign-in screen lists demo employees (this is a simulated IdP)."""
    return {"users": list(EMPLOYEES.values()), "password_hint": DEMO_PASSWORD}


class Login(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: Login):
    if body.username not in EMPLOYEES or body.password != DEMO_PASSWORD:
        raise HTTPException(401, "Invalid username or password")
    return {"access_token": issue_employee_token(body.username), "user": EMPLOYEES[body.username]}


@router.get("/me")
def me(employee: dict = Depends(current_employee)):
    return {k: v for k, v in employee.items() if k != "token"}
