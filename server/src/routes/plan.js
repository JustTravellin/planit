import { Router } from "express";
import { store } from "../store.js";

export const planRouter = Router();

planRouter.get("/", (req, res) => {
  res.json({
    plan: req.plan,
    me: { name: req.invite.name, role: req.invite.role },
  });
});

const EDITABLE_FIELDS = [
  "title",
  "eventDate",
  "startTime",
  "endTime",
  "address",
  "hosts",
  "guestsOfHonour",
  "expectedGuestCount",
  "theme",
  "notes",
];

planRouter.patch("/", (req, res) => {
  const patch = {};
  for (const field of EDITABLE_FIELDS) {
    if (field in req.body) patch[field] = req.body[field];
  }
  const updated = store.updatePlan(req.plan.id, patch);
  res.json(updated);
});
