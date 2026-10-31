// Brings MongoDB to Alembic revision 01f3a918b5dd: notice templates lose their context class.
// MSS applies it on start; by hand, with MSS stopped: mongosh "<mongodb url>/<database>" <this file>
load(require("path").join(__dirname, "apply.js"));
applyMigration("01f3a918b5dd_drop_the_context_class_of_notice_templates.json", "upgrade");
