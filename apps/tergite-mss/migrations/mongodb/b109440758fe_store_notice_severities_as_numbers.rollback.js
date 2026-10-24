// Undoes b109440758fe_store_notice_severities_as_numbers.upgrade.js: severities become names.
// With MSS stopped: mongosh "<mongodb url>/<database>" <this file>, then start the older MSS.
load(require("path").join(__dirname, "apply.js"));
applyMigration("b109440758fe_store_notice_severities_as_numbers.json", "rollback");
