// Force the list-view + form indicator to read from doc.status instead of
// docstatus. Frappe v15's default behaviour shows "Draft" for any docstatus=0
// doc regardless of the workflow state — this override fixes that so the pill
// reflects the actual workflow state (Under Review / Approved / On Hold / etc).
frappe.listview_settings["Implementation Estimate"] = {
	get_indicator(doc) {
		const status = doc.status || "Draft";
		const colors = {
			"Draft":              "blue",
			"Under Review":       "orange",
			"Revision Requested": "red",
			"Approved":           "green",
			"Won":                "darkgreen",
			"Lost":               "gray",
			"On Hold":            "yellow",
			"Delivered":          "purple",
		};
		return [__(status), colors[status] || "gray", `status,=,${status}`];
	}
};
