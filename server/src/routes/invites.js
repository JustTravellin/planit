import { Router } from "express";
import { store, id, token } from "../store.js";
import { requireOwner } from "../middleware/auth.js";

export const invitesRouter = Router();

function publicInvite(invite, baseUrl) {
  return {
    id: invite.id,
    name: invite.name,
    role: invite.role,
    revoked: invite.revoked,
    createdAt: invite.createdAt,
    link: `${baseUrl}/p/${invite.token}`,
  };
}

// Only the owner can see or manage who else has a link, and it's the only
// route in the whole app that lists people rather than party details.
invitesRouter.get("/", requireOwner, (req, res) => {
  const baseUrl = req.query.baseUrl || "";
  const invites = store.listInvites(req.plan.id).map((i) => publicInvite(i, baseUrl));
  res.json(invites);
});

invitesRouter.post("/", requireOwner, (req, res) => {
  const { name, role = "collaborator", baseUrl = "" } = req.body;
  if (!name) return res.status(400).json({ error: "name is required" });
  if (!["owner", "collaborator"].includes(role)) {
    return res.status(400).json({ error: "role must be owner or collaborator" });
  }

  const invite = {
    id: id(),
    planId: req.plan.id,
    token: token(),
    name,
    role,
    revoked: false,
    createdAt: new Date().toISOString(),
  };
  store.createInvite(invite);
  res.status(201).json(publicInvite(invite, baseUrl));
});

invitesRouter.patch("/:inviteId", requireOwner, (req, res) => {
  const { revoked } = req.body;
  const updated = store.updateInvite(req.params.inviteId, req.plan.id, { revoked: !!revoked });
  if (!updated) return res.status(404).json({ error: "not found" });
  res.json(publicInvite(updated, req.body.baseUrl || ""));
});
