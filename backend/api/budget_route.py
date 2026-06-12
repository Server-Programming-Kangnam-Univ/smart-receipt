from fastapi import APIRouter
from services import budget_service

router = APIRouter()

@router.get("/budget/")
def get_budget():
    return budget_service.get_budget()

@router.post("/budget/")
def update_budget(payload: dict):
    budget = payload.get("budget", 1000000)
    return budget_service.update_budget(budget)
