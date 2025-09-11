from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import operator, json
from datetime import datetime
from sqlalchemy import create_engine, text
from urllib import parse
from dotenv import load_dotenv
import os
load_dotenv(".environment")

sqlServer = os.getenv("SQL_SERVER")
sqlPort = os.getenv("SQL_PORT")
sqlUsername = os.getenv("SQL_USERNAME")
sqlPassword = os.getenv("SQL_PASSWORD")
sqlDatabase = os.getenv("SQL_DB")
password = parse.quote_plus(sqlPassword)

app = FastAPI()


connection_string = (
    f"mssql+pyodbc://{sqlUsername}:{sqlPassword}"
    f"@{sqlServer}/{sqlDatabase}?driver=ODBC Driver 17 for SQL Server"
)


engine = create_engine(connection_string)

print("connection established with DB")
# ---------- IN-MEMORY VARIABLES ----------
VARIABLES: Dict[str, str] = {}

# Operators map
OPS = {
    "equal to": operator.eq,
    "not equal to": operator.ne,
    "less than": operator.lt,
    "less than or equal to": operator.le,
    "greater than": operator.gt,
    "greater than or equal to": operator.ge,
    "in": lambda a, b: a in b,
    "not in": lambda a, b: a not in b,
}


# ---------- MODELS ----------
class Condition(BaseModel):
    field: str
    operator: str
    lit_value: Optional[str] = None
    variable: Optional[str] = None

class Rule(BaseModel):
    rule_name: str
    conditions: List[Condition]
    logic: str
    action: str

class Variable(BaseModel):
    name: str
    expression: str  

class Record(BaseModel):
    data: Dict[str, Any]


# ---------- VARIABLE CRUD (still in-memory for now) ----------
# @app.get("/variables")
# def get_variables():
#     return {"variables": [{"name": k, "expression": v} for k, v in VARIABLES.items()]}

@app.post("/variables")
def add_variable(var: Variable):
    if var.name in VARIABLES:
        raise HTTPException(status_code=400, detail=f"Variable '{var.name}' already exists.")
    VARIABLES[var.name] = var.expression
    return {"message": f"Variable '{var.name}' added."}


# ---------- RULE CRUD (SQL SERVER) ----------
@app.get("/rules")
def get_rules():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT rule_name, conditions, logic, action FROM RuleManagement"))
        rules = [
            {
                "rule_name": row.rule_name,
                "conditions": json.loads(row.conditions),
                "logic": row.logic,
                "action": row.action
            }
            for row in result
        ]
    return {"rules": rules}

@app.post("/rules")
def add_rule(rule: Rule):
    with engine.connect() as conn:
        # check duplicate
        exists = conn.execute(text("SELECT COUNT(*) FROM RuleManagement WHERE rule_name=:name"), {"name": rule.rule_name}).scalar()
        if exists > 0:
            raise HTTPException(status_code=400, detail=f"Rule '{rule.rule_name}' already exists.")
        
        conn.execute(
            text("INSERT INTO RuleManagement (rule_name, conditions, logic, action) VALUES (:name, :conds, :logic, :action)"),
            {
                "name": rule.rule_name,
                "conds": json.dumps([c.dict() for c in rule.conditions]),
                "logic": rule.logic,
                "action": rule.action
            }
        )
        conn.commit()
    return {"message": f"Rule '{rule.rule_name}' added."}

@app.put("/rules/{rule_name}")
def update_rule(rule_name: str, rule: Rule):
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT COUNT(*) FROM RuleManagement WHERE rule_name=:name"),
            {"name": rule_name}
        ).scalar()

        if result == 0:
            raise HTTPException(status_code=404, detail=f"Rule '{rule_name}' not found.")

        conn.execute(
            text("""
                UPDATE RuleManagement
                SET rule_name=:new_name,
                    conditions=:conds,
                    logic=:logic,
                    action=:action
                WHERE rule_name=:old_name
            """),
            {
                "new_name": rule.rule_name,  # allow renaming the rule
                "conds": json.dumps([c.dict() for c in rule.conditions]),
                "logic": rule.logic,
                "action": rule.action,
                "old_name": rule_name
            }
        )
        conn.commit()

    return {"message": f"Rule '{rule_name}' updated."}

@app.delete("/rules/{rule_name}")
def delete_rule(rule_name: str):
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM RuleManagement WHERE rule_name=:name"), {"name": rule_name}).scalar()
        if result == 0:
            raise HTTPException(status_code=404, detail=f"Rule '{rule_name}' not found.")
        
        conn.execute(text("DELETE FROM RuleManagement WHERE rule_name=:name"), {"name": rule_name})
        conn.commit()
    return {"message": f"Rule '{rule_name}' deleted."}


# ---------- EVALUATION ----------
@app.post("/evaluate")
def evaluate(record: Record):
    evaluated = {}

    # compute derived variables
    for name, expr in VARIABLES.items():
        if "-" in expr:
            left, right = [x.strip() for x in expr.split("-")]
            left_val = datetime.fromisoformat(record.data[left])
            right_val = datetime.fromisoformat(record.data[right])
            VARIABLES[name] = (left_val - right_val).days
            record.data[name] = VARIABLES[name]

    # fetch rules from DB
    with engine.connect() as conn:
        result = conn.execute(text("SELECT rule_name, conditions, logic, action FROM RuleManagement"))
        rules = [
            {
                "rule_name": row.rule_name,
                "conditions": json.loads(row.conditions),
                "logic": row.logic,
                "action": row.action
            }
            for row in result
        ]

    # check rules
    for rule in rules:
        results = []
        for cond in rule["conditions"]:
            op = OPS[cond["operator"]]
            field = cond["field"]
            lit_value = cond.get("lit_value")
            variable = cond.get("variable")

            if variable:
                comp_value = record.data.get(variable)
            elif lit_value not in (None, "", "null"):
                try:
                    comp_value = int(lit_value)
                except:
                    comp_value = str(lit_value)
            else:
                continue
            results.append(op(record.data[field], comp_value))

        if rule["logic"] == "AND":
            passed = all(results)
        elif rule["logic"] == "OR":
            passed = any(results)
        else:
            passed = any(results)

        if passed:
            evaluated[rule["rule_name"]] = rule["action"]

    return {"evaluated": evaluated}

@app.post("/evaluate_rule/{rule_name}")
def evaluate_single_rule(rule_name: str, record: Record):
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT rule_name, conditions, logic, action FROM RuleManagement WHERE rule_name=:name"),
            {"name": rule_name}
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail=f"Rule '{rule_name}' not found.")

        rule = {
            "rule_name": row.rule_name,
            "conditions": json.loads(row.conditions),
            "logic": row.logic,
            "action": row.action
        }

    # --- evaluate only this rule ---
    results = []
    for cond in rule["conditions"]:
        op = OPS[cond["operator"]]
        field = cond["field"]
        lit_value = cond.get("lit_value")
        variable = cond.get("variable")

        if variable:
            comp_value = record.data.get(variable)
        elif lit_value not in (None, "", "null"):
            try:
                comp_value = int(lit_value)
            except:
                comp_value = str(lit_value)
        else:
            continue

        results.append(op(record.data[field], comp_value))

    if rule["logic"] == "AND":
        passed = all(results)
    elif rule["logic"] == "OR":
        passed = any(results)
    else:
        passed = any(results)

    return {
        "rule_name": rule["rule_name"],
        "passed": passed,
        "action": rule["action"] if passed else None
    }

@app.get("/operators")
def get_operators():
    return {"operators": list(OPS.keys())}

@app.get("/variables")
def get_variables():
    # return {"operators": list(OPS.keys())}
    return {"variables":["claim_amount","approved_amount","diagnosis","icd_code","name"]}
