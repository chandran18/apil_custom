frappe.listview_settings["Extrusion Log"] = {
	onload: function (listview) {
		listview.page.add_inner_button("Workflow Docs", function () {
			window.open("/private/files/Extrusion Log - Stock Entry Workflow.pdf", "_blank");
		});
	},
};
