import os
import json

BUDGET_FILE = "budget.json"

def init_budget_storage():
    if not os.path.exists(BUDGET_FILE):
        with open(BUDGET_FILE, "w", encoding="utf-8") as f:
            json.dump({"budget": 1000000}, f)

def get_budget():
    with open(BUDGET_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def update_budget(new_budget: int):
    with open(BUDGET_FILE, "w", encoding="utf-8") as f:
        json.dump({"budget": new_budget}, f)
    return {"message": "예산이 업데이트되었습니다.", "budget": new_budget}
