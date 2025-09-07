import streamlit as st
import requests


BASE_URL = "http://localhost:8000"

st.set_page_config(page_title="Rule Builder", layout="centered")

st.title("🛠️ Python Rule Builder (No-Code)")

listOfVariables = ["claim_amount","approved_amount","sum_insured","diagnosis","date_of_admission","date_of_discharge","icd_code"]
vars_res = {"variables":listOfVariables}


# ----------------- RULES -----------------
st.header("➕ Create New Rule")
rule_name = st.text_input("Rule Name")
action = st.text_input("Action (e.g., flag_fraud)")

st.subheader("Add Conditions")
conditions = []
if "conds" not in st.session_state:
    st.session_state.conds = []

field = st.selectbox("Field Name", listOfVariables, None)
operator = st.selectbox("Operator", ["equal to", "not equal to", "less than", "less than or equal to", "greater than", "greater than or equal to","not in","in"])
lit_value = st.text_input("Value (number)")
variable = st.selectbox("Variable (name)", listOfVariables, None)
logic = st.selectbox("Append condition", ["","AND", "OR"])

if st.button("Add Condition"):
    condition = {
        "field": field,
        "operator": operator,
        "variable": variable if variable else None,
        "lit_value": int(lit_value) if lit_value.strip() else None
    }
    st.session_state.conds.append(condition)

st.write("### Current Conditions")
st.json(st.session_state.conds)

if st.button("Save Rule"):
    if rule_name and st.session_state.conds:
        res = requests.post(f"{BASE_URL}/rules", json={
            "rule_name": rule_name,
            "conditions": st.session_state.conds,
            "logic": logic,
            "action": action
        })

        st.success(res.json()["message"])
        st.session_state.conds = []

# ----------------- TEST -----------------
st.header("🔍 Test Rules on Sample Record")
sample_json = st.text_area("Enter JSON record", 
"""
{
    "admission_date": "2025-08-01",
    "discharge_date": "2025-08-15",
    "claim_amount": 1000,
    "approved_amount":1000,
    "diagnosis": "D01",
    "mapped_procedure": "P01"
}
""")

if st.button("Evaluate Record"):
    try:
        res = requests.post(f"{BASE_URL}/evaluate", json={"data": eval(sample_json)})
        st.json(res.json())
    except Exception as e:
        st.error(f"Error: {e}")


# ----------------- VARIABLES -----------------
# st.header("➕ Add New Variable")
# var_name = st.text_input("Variable Name (e.g., LOS)")
# var_expr = st.text_input("Expression (e.g., discharge_date - admission_date)")
# if st.button("Save Variable"):
#     if var_name and var_expr:
#         res = requests.post(f"{BASE_URL}/variables", json={"name": var_name, "expression": var_expr})
#         st.success(res.json()["message"])

# # Show existing variables
# st.subheader("Available Variables")
# # vars_res = requests.get(f"{BASE_URL}/variables").json()

# st.write(vars_res["variables"])
