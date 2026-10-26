import { Router } from "express";
import cors from "cors";
import { createCookieHeader, mockDb, respond401, forwardAsyncErrors } from "../utils";
import { User } from "../types";

const apiBaseUrl = process.env.VITE_API_BASE_URL;
const appHostname = new URL(apiBaseUrl as string).hostname;
const userIdCookieName = process.env.USER_ID_COOKIE_NAME ?? "userId";

const router = Router();

router.use(
  cors({
    origin: [new RegExp(`${appHostname.replace(/\./g, "\\.")}(:\\d+)?$`)],
    methods: ["GET", "PUT", "POST", "DELETE", "PATCH", "HEAD"],
    credentials: true,
  })
);

router.options("*", (req, res, next) => {
  next();
});

// Dummy third party authenticator GET page
router.get(
  "/callback",
  forwardAsyncErrors(async (req, res) => {
    const userId = req.cookies[userIdCookieName];
    if (!userId) {
      return res.render("oauth", {});
    }

    const user = mockDb.getOne<User>("users", (v) => v.id === userId);
    if (user) {
      const { next: nextUrl } = req.query;
      const cookieHeader = await createCookieHeader(user);
      res.set("Set-Cookie", cookieHeader);
      return res.redirect(nextUrl as string);
    }
    return respond401(res);
  })
);

// Dummy third party authenticator POST page
router.post(
  "/callback",
  forwardAsyncErrors(async (req, res) => {
    const { email } = req.body;

    const user = mockDb.getOne<User>("users", (v) => v.email === email);
    if (user) {
      const { next: nextUrl } = req.query;
      const cookieHeader = await createCookieHeader(user);
      res.set("Set-Cookie", cookieHeader);
      return res.redirect(nextUrl as string);
    }
    return res.render("oauth", { emailError: "unknown email" });
  })
);

export default router;
