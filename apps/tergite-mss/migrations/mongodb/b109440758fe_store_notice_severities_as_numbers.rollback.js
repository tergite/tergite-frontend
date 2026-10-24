// Undoes b109440758fe_store_notice_severities_as_numbers.upgrade.js: severities become names.
// With MSS stopped: mongosh "<mongodb url>/<database>" <this file>, then start the older MSS.
// It bypasses the current validator, which allows only the numbers, so the user needs the
// bypassDocumentValidation privilege, e.g. dbAdmin. Running it twice is harmless.

const numbersToNames = [
  {
    $set: {
      severity: {
        $switch: {
          branches: [
            { case: { $eq: ["$severity", 1] }, then: "critical" },
            { case: { $eq: ["$severity", 2] }, then: "warning" },
          ],
          default: "info",
        },
      },
    },
  },
];
const options = { bypassDocumentValidation: true };

const notices = db.notices.updateMany(
  { severity: { $type: "number" } },
  numbersToNames,
  options
);
const templates = db.notice_templates.updateMany(
  { severity: { $type: "number" } },
  numbersToNames,
  options
);
print(
  `notices: ${notices.modifiedCount}, notice_templates: ${templates.modifiedCount} converted`
);
