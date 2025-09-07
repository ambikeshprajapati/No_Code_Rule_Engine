from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Union
import operator
from datetime import datetime

app = FastAPI()

# In-memory stores
VARIABLES: Dict[str, str] = {}

# Rule = Dict[str, Union[str, int, None]]
# RULES: List[Rule] = []

RULES: List[Dict[str, Any]] = []

# Operators map
OPS = OPERATOR_MAP = {
    "equal to": operator.eq,
    "not equal to": operator.ne,
    "less than": operator.lt,
    "less than or equal to": operator.le,
    "greater than": operator.gt,
    "greater than or equal to": operator.ge,
    "in": lambda a, b: a in b,
    "not in": lambda a, b: a not in b,
}

# --------- MODELS ----------
class Condition(BaseModel):
    field: str
    operator: str
    lit_value: Optional[str] = None
    variable: Optional[str] = None

class Rule(BaseModel):
    rule_name: str
    conditions: List[Condition]
    logic: str  # AND / OR
    action: str

class Variable(BaseModel):
    name: str
    expression: str  # e.g. "discharge_date - admission_date"

class Record(BaseModel):
    data: Dict[str, Any]


# --------- ENDPOINTS ----------

@app.get("/variables")
def get_variables():
    return {"variables": list(VARIABLES.keys())}

@app.post("/variables")
def add_variable(var: Variable):
    VARIABLES[var.name] = var.expression
    return {"message": f"Variable '{var.name}' added."}

@app.get("/rules")
def get_rules():
    return {"rules": RULES}

@app.post("/rules")
def add_rule(rule: Rule):
    RULES.append(rule.dict())
    return {"message": f"Rule '{rule.rule_name}' added."}

@app.post("/evaluate")
def evaluate(record: Record):
    evaluated = {}

    # compute derived variables
    for name, expr in VARIABLES.items():
        if "-" in expr:  # very basic example
            left, right = [x.strip() for x in expr.split("-")]
            left_val = datetime.fromisoformat(record.data[left])
            right_val = datetime.fromisoformat(record.data[right])
            VARIABLES[name] = (left_val - right_val).days
            record.data[name] = VARIABLES[name]

    # check each rule
    for rule in RULES:
        results = []
        for cond in rule["conditions"]:
            op = OPS[cond["operator"]]
            field = cond["field"]
            lit_value = cond.get("lit_value")
            variable = cond.get("variable")
            # Decide comparison value
            if variable:  
                comp_value = record.data.get(variable)
                print(record.data)
            elif lit_value not in (None, "", "null"):
                if op in ["less than", "less than or equal to", "greater than", "greater than or equal to"]:
                    comp_value = int(lit_value)
                else:
                    try:
                        comp_value = int(lit_value)
                    except:
                        comp_value = str(lit_value)
                print(comp_value)
            else:
                # Skip if neither lit_value nor variable is provided
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
