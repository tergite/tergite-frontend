// Undoes 01f3a918b5dd_drop_the_context_class_of_notice_templates.upgrade.js, which only removed a field the older MSS has a default for.
// With MSS stopped: mongosh "<mongodb url>/<database>" <this file>, then start the older MSS.
load(require("path").join(__dirname, "apply.js"));
applyMigration("01f3a918b5dd_drop_the_context_class_of_notice_templates.json", "rollback");
