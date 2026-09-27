import { store } from "../store.js";

// Every request must carry a per-person invite token (from their unique
// link). There is no login form and no plan listing — the token is the
// entire access model, which is what makes this "secret": you can only get
// in if someone who already has access sent you a link.
export function requireInvite(req, res, next) {
  const header = req.headers.authorization || "";
  const bearer = header.startsWith("Bearer ") ? header.slice(7) : null;
  const t = bearer || req.query.token;

  if (!t) return res.status(401).json({ error: "missing invite token" });

  const invite = store.getInviteByToken(t);
  if (!invite || invite.revoked) {
    return res.status(401).json({ error: "invalid or revoked invite link" });
  }

  const plan = store.getPlan(invite.planId);
  if (!plan) return res.status(401).json({ error: "plan no longer exists" });

  req.invite = invite;
  req.plan = plan;
  next();
}

export function requireOwner(req, res, next) {
  if (req.invite.role !== "owner") {
    return res.status(403).json({ error: "only the plan owner can do this" });
  }
  next();
}
