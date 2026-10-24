// Applies one direction of a migration's JSON beside it and records it, as
// `python -m migrations.mongodb` does, so MSS will not apply it again on start.
// It bypasses the validator of the MSS stopped or about to start, which refuses one of
// the forms, so the user needs the bypassDocumentValidation privilege, e.g. dbAdmin.

const fs = require("fs");
const path = require("path");

function applyMigration(fileName, direction) {
  const revision = fileName.split("_")[0];
  const migration = EJSON.parse(
    fs.readFileSync(path.join(__dirname, fileName), "utf8")
  );
  for (const { collection, filter, update } of migration[direction]) {
    const result = db
      .getCollection(collection)
      .updateMany(filter, update, { bypassDocumentValidation: true });
    print(`${collection}: ${result.modifiedCount} changed`);
  }
  if (direction === "upgrade") {
    db.mongodb_migrations.updateOne(
      { _id: revision },
      { $set: { applied_at: new Date() } },
      { upsert: true }
    );
  } else {
    db.mongodb_migrations.deleteOne({ _id: revision });
  }
}
