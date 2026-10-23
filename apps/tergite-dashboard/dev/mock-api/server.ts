/**
 * A mock server to use when running tests
 *
 * I am tired of libraries that work only upto some point, then start failing.
 */

import express, { ErrorRequestHandler } from "express";
import cookieParser from "cookie-parser";
import { toHTTPError, NotFound } from "./utils";
import path from "path";
import { fileURLToPath } from "url";
import logger from "morgan";
import oauthRouter from "./routes/oauth";
import generalRouter from "./routes/general";

// "type": "module" in the package.json makes this an ES module, making it __filename
// and __dirname undefined, which they would be if this were a commonjs module
// Thanks to https://iamwebwiz.medium.com/how-to-fix-dirname-is-not-defined-in-es-module-scope-34d94a86694d
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const apiPort = parseInt(process.env.API_PORT ?? "8002");

const app = express();

app.use(logger("dev") as express.RequestHandler);
app.use(express.urlencoded({ extended: false }));
app.use(cookieParser());
app.use(express.json());
app.set("views", path.join(__dirname, "views"));
app.set("view engine", "hbs");

app.use("/", generalRouter);
app.use("/oauth", oauthRouter);

// catch 404 and forward to error handler
app.use(function (req, res, next) {
  next(NotFound());
});

// error handler
app.use(function (err, req, res) {
  // set locals, only providing error in development
  res.locals.message = err.message;
  res.locals.error = req.app.get("env") === "development" ? err : {};

  const error = toHTTPError(err);

  // render the error page
  res.status(error.status);
  res.json({ detail: error.message });
} as ErrorRequestHandler);

app.listen(apiPort, "0.0.0.0", () => {
  console.log(`api running on port ${apiPort}`);
});
