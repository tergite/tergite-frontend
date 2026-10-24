// Brings MongoDB to Alembic revision b109440758fe: notice severities become numbers.
// MSS applies it on start; by hand, with MSS stopped: mongosh "<mongodb url>/<database>" <this file>
load(require("path").join(__dirname, "apply.js"));
applyMigration("b109440758fe_store_notice_severities_as_numbers.json", "upgrade");
