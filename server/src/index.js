import express from "express";
import cors from "cors";
import { requireInvite } from "./middleware/auth.js";
import { planRouter } from "./routes/plan.js";
import { invitesRouter } from "./routes/invites.js";
import { collectionRouter } from "./routes/collection.js";
import { COLLECTIONS } from "./store.js";

const app = express();
app.use(cors());
app.use(express.json());

app.get("/api/health", (req, res) => res.json({ ok: true }));

// Every /api route below this point needs a valid invite token; there is
// deliberately no endpoint that lists or discovers plans.
app.use("/api", requireInvite);
app.use("/api/plan", planRouter);
app.use("/api/invites", invitesRouter);
for (const collection of COLLECTIONS) {
  app.use(`/api/${collection}`, collectionRouter(collection));
}

const port = process.env.PORT || 4700;
app.listen(port, () => {
  console.log(`URBOS celebrations planner API listening on :${port}`);
});
