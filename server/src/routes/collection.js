import { Router } from "express";
import { store, id } from "../store.js";

// Run sheet, zones, guests, vendors, shopping list, tasks and contacts are
// all "a list of records the household edits together" with the same
// shape of operations, so they share one CRUD implementation instead of
// seven near-identical route files.
export function collectionRouter(collection) {
  const router = Router();

  router.get("/", (req, res) => {
    res.json(store.list(collection, req.plan.id));
  });

  router.post("/", (req, res) => {
    const item = {
      id: id(),
      ...req.body,
      createdBy: req.invite.name,
      createdAt: new Date().toISOString(),
    };
    store.create(collection, req.plan.id, item);
    res.status(201).json(item);
  });

  router.patch("/:itemId", (req, res) => {
    const updated = store.update(collection, req.plan.id, req.params.itemId, req.body);
    if (!updated) return res.status(404).json({ error: "not found" });
    res.json(updated);
  });

  router.delete("/:itemId", (req, res) => {
    const ok = store.remove(collection, req.plan.id, req.params.itemId);
    if (!ok) return res.status(404).json({ error: "not found" });
    res.status(204).end();
  });

  return router;
}
