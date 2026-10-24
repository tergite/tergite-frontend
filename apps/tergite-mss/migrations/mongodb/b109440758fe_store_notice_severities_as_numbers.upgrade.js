// MongoDB's side of Alembic revision b109440758fe: notice severities become numbers.
// With MSS stopped: mongosh "<mongodb url>/<database>" <this file>
// It bypasses the validator of the MSS being replaced, which allows only the names, so the
// user needs the bypassDocumentValidation privilege, e.g. dbAdmin. Running it twice is harmless.

const namesToNumbers = [
  {
    $set: {
      severity: {
        $switch: {
          branches: [
            { case: { $eq: ["$severity", "critical"] }, then: 1 },
            { case: { $eq: ["$severity", "warning"] }, then: 2 },
          ],
          default: 3,
        },
      },
    },
  },
  // v2026.06.0 stored it beside the name
  { $unset: "severity_number" },
];
const options = { bypassDocumentValidation: true };

const notices = db.notices.updateMany(
  { severity: { $type: "string" } },
  namesToNumbers,
  options
);
const templates = db.notice_templates.updateMany(
  { severity: { $type: "string" } },
  namesToNumbers,
  options
);
print(
  `notices: ${notices.modifiedCount}, notice_templates: ${templates.modifiedCount} converted`
);
