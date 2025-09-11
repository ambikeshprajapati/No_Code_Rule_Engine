import streamlit as st
import requests

BASE_URL = "http://localhost:8000"

st.set_page_config(page_title="Rule Builder", layout="wide")

st.title("🛠️ Python Rule Builder (No-Code)")

# ----------------- HELPER FUNCTIONS -----------------
def fetch_rules():
    try:
        return requests.get(f"{BASE_URL}/rules").json().get("rules", [])
    except:
        return []

def fetch_variables():
    try:
        return requests.get(f"{BASE_URL}/variables").json().get("variables", [])
    except:
        return []


# ----------------- RULES -----------------
st.header("➕ Create New Rule")
rule_name = st.text_input("Rule Name")
action = st.text_input("Action (e.g., flag_fraud)")

st.subheader("Add Conditions")
if "conds" not in st.session_state:
    st.session_state.conds = []

all_vars = fetch_variables()
listOfVariables = ["claim_amount", "approved_amount", "sum_insured", "diagnosis", 
                   "date_of_admission", "date_of_discharge", "icd_code"]

field = st.selectbox("Field Name", listOfVariables)
operator = st.selectbox("Operator", [
    "equal to", "not equal to", "less than", "less than or equal to",
    "greater than", "greater than or equal to", "not in", "in"
])
lit_value = st.text_input("Literal Value (number/string)")
variable = st.selectbox("Variable (optional)",[None] + listOfVariables)
logic = st.selectbox("Condition Logic", ["AND", "OR"])

if st.button("Add Condition"):
    condition = {
        "field": field,
        "operator": operator,
        "variable": variable if variable else None,
        "lit_value": lit_value if lit_value.strip() else None
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

# ----------------- MANAGE RULES -----------------
st.header("📋 Manage Rules")
rules = fetch_rules()

if rules:
    for r in rules:
        with st.expander(f"Rule: {r['rule_name']}"):
            st.subheader("Edit Rule")

            # Editable rule name
            new_name = st.text_input(
                f"Rule Name ({r['rule_name']})",
                value=r["rule_name"],
                key=f"name_{r['rule_name']}"
            )

            # Editable conditions
            st.write("### Conditions")
            updated_conditions = []
            for idx, cond in enumerate(r["conditions"]):
                st.markdown(f"**Condition {idx+1}**")

                field = st.selectbox(
                    "Field", 
                    listOfVariables, 
                    index=listOfVariables.index(cond["field"]) if cond["field"] in listOfVariables else 0,
                    key=f"field_{r['rule_name']}_{idx}"
                )

                operator = st.selectbox(
                    "Operator",
                    [
                        "equal to", "not equal to", "less than", "less than or equal to",
                        "greater than", "greater than or equal to", "not in", "in"
                    ],
                    index=[
                        "equal to", "not equal to", "less than", "less than or equal to",
                        "greater than", "greater than or equal to", "not in", "in"
                    ].index(cond["operator"]),
                    key=f"op_{r['rule_name']}_{idx}"
                )

                lit_value = st.text_input(
                    "Literal Value", 
                    cond.get("lit_value", ""), 
                    key=f"lit_{r['rule_name']}_{idx}"
                )

                variable = st.selectbox(
                    "Variable (optional)",
                    [""] + listOfVariables,
                    index=([""] + listOfVariables).index(cond.get("variable", "")) if cond.get("variable") else 0,
                    key=f"var_{r['rule_name']}_{idx}"
                )

                updated_conditions.append({
                    "field": field,
                    "operator": operator,
                    "lit_value": lit_value if lit_value != "" else None,
                    "variable": variable if variable != "" else None
                })

            # Add new condition
            if st.button(f"➕ Add Condition to {r['rule_name']}", key=f"add_cond_{r['rule_name']}"):
                updated_conditions.append({
                    "field": listOfVariables[0],
                    "operator": "equal to",
                    "lit_value": None,
                    "variable": None
                })

            # Editable logic
            logic = st.selectbox(
                "Logic", ["AND", "OR"],
                index=["AND", "OR"].index(r["logic"]),
                key=f"logic_{r['rule_name']}"
            )

            # Editable action
            action = st.text_input(
                "Action",
                value=r["action"],
                key=f"action_{r['rule_name']}"
            )

            # Save changes
            if st.button(f"💾 Update {r['rule_name']}", key=f"update_{r['rule_name']}"):
                updated_rule = {
                    "rule_name": new_name,
                    "conditions": updated_conditions,
                    "logic": logic,
                    "action": action
                }
                res = requests.put(f"{BASE_URL}/rules/{r['rule_name']}", json=updated_rule)
                st.success(res.json()["message"])

            # Delete rule
            if st.button(f"🗑️ Delete {r['rule_name']}", key=f"delete_{r['rule_name']}"):
                res = requests.delete(f"{BASE_URL}/rules/{r['rule_name']}")
                st.warning(res.json()["message"])

            # --- Test Rule ---
            st.subheader(f"🔍 Test {r['rule_name']}")
            sample_json = st.text_area(
                f"Enter JSON record for {r['rule_name']}",
                """
{
    "date_of_admission": "2025-08-01",
    "date_of_discharge": "2025-08-15",
    "claim_amount": 1000,
    "approved_amount": 1000,
    "diagnosis": "D01",
    "icd_code": "C123"
}
""",
                key=f"test_input_{r['rule_name']}"
            )

            if st.button(f"Run Test for {r['rule_name']}", key=f"test_btn_{r['rule_name']}"):
                try:
                    res = requests.post(
                        f"{BASE_URL}/evaluate_rule/{r['rule_name']}",
                        json={"data": eval(sample_json)}
                    )
                    st.json(res.json())
                except Exception as e:
                    st.error(f"Error: {e}")
else:
    st.info("No rules found.")


# ----------------- TEST -----------------
# st.header("🔍 Test Rules on Sample Record")
# sample_json = st.text_area("Enter JSON record", 
# """
# {
#     "date_of_admission": "2025-08-01",
#     "date_of_discharge": "2025-08-15",
#     "claim_amount": 1000,
#     "approved_amount": 1000,
#     "diagnosis": "D01",
#     "icd_code": "C123"
# }
# """)

# if st.button("Evaluate Record"):
#     try:
#         res = requests.post(f"{BASE_URL}/evaluate", json={"data": eval(sample_json)})
#         st.json(res.json())
#     except Exception as e:
#         st.error(f"Error: {e}")


# ----------------- VARIABLES -----------------
# st.header("➕ Add / Manage Variables")
# var_name = st.text_input("Variable Name (e.g., LOS)")
# var_expr = st.text_input("Expression (e.g., date_of_discharge - date_of_admission)")

# col1, col2 = st.columns(2)
# with col1:
#     if st.button("Save Variable"):
#         if var_name and var_expr:
#             res = requests.post(f"{BASE_URL}/variables", json={"name": var_name, "expression": var_expr})
#             st.success(res.json()["message"])

# with col2:
#     if st.button("Update Variable"):
#         if var_name and var_expr:
#             res = requests.put(f"{BASE_URL}/variables/{var_name}", json={"name": var_name, "expression": var_expr})
#             st.info(res.json()["message"])

# # Show existing variables
# st.subheader("Available Variables")
# variables = fetch_variables()
# if variables:
#     for v in variables:
#         col1, col2 = st.columns([3,1])
#         with col1:
#             st.write(f"📌 **{v['name']}** = `{v['expression']}`")
#         with col2:
#             if st.button(f"Delete {v['name']}", key=f"del_{v['name']}"):
#                 res = requests.delete(f"{BASE_URL}/variables/{v['name']}")
#                 st.warning(res.json()["message"])
# else:
#     st.info("No variables defined yet.")
