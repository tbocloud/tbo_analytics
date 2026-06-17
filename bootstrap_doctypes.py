import frappe

frappe.init(site="erp.hydrotech", sites_path="/Users/sanikacs/frappe-bench/sites")
frappe.connect()

# Ensure the module is registered
if not frappe.db.exists("Module Def", "tbo analytics"):
    m = frappe.new_doc("Module Def")
    m.module_name = "tbo analytics"
    m.app_name = "tbo_analytics"
    m.flags.ignore_permissions = True
    m.insert(ignore_if_duplicate=True)
    frappe.db.commit()
    print("Created Module Def: tbo analytics")
else:
    print("Module Def already exists")

doctypes = [
    "ERP Module Master",
    "Integration Type Master",
    "Module Selection",
    "Custom Module Request",
    "Integration Requirement",
    "Team Composition",
    "Team Revision",
    "Direct Cost Item",
    "Indirect Cost Item",
    "Infrastructure Cost Item",
    "Implementation Estimate",
]

for dn in doctypes:
    try:
        frappe.reload_doc("tbo analytics", "DocType", dn, force=True)
        frappe.db.commit()
        print(f"OK: {dn}")
    except Exception as e:
        print(f"FAIL: {dn} -> {e}")

reports = [
    "Time Coverage Tracker",
    "Estimate vs Actual Hours",
    "Profitability Scenarios",
    "Project Cost Breakdown",
]
for dn in reports:
    try:
        frappe.reload_doc("tbo analytics", "Report", dn, force=True)
        frappe.db.commit()
        print(f"OK report: {dn}")
    except Exception as e:
        print(f"FAIL report: {dn} -> {e}")

print("All done.")
frappe.destroy()
