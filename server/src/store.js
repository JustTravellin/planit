import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DATA_DIR = process.env.URBOS_DATA_DIR || path.join(__dirname, "..", "data");
const DATA_FILE = path.join(DATA_DIR, "db.json");

const COLLECTIONS = [
  "runsheet",
  "zones",
  "guests",
  "vendors",
  "shopping",
  "tasks",
  "contacts",
];

function emptyDb() {
  const db = { plans: {}, invites: {} };
  for (const c of COLLECTIONS) db[c] = {};
  return db;
}

function load() {
  if (!fs.existsSync(DATA_FILE)) return emptyDb();
  const raw = fs.readFileSync(DATA_FILE, "utf8");
  if (!raw.trim()) return emptyDb();
  const parsed = JSON.parse(raw);
  const db = emptyDb();
  Object.assign(db, parsed);
  for (const c of COLLECTIONS) db[c] = parsed[c] || {};
  return db;
}

function persist(db) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
  const tmp = `${DATA_FILE}.${process.pid}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(db, null, 2));
  fs.renameSync(tmp, DATA_FILE);
}

// Single in-memory copy, written to disk after every mutation. Traffic on
// this app is a handful of family members editing a party plan, so a plain
// synchronous read-modify-write (Node's event loop already serializes it)
// is plenty — no need for a real database or locking.
let db = load();

export function id() {
  return crypto.randomBytes(9).toString("base64url");
}

export function token() {
  return crypto.randomBytes(24).toString("base64url");
}

export const store = {
  raw() {
    return db;
  },

  getPlan(planId) {
    return db.plans[planId] || null;
  },
  createPlan(plan) {
    db.plans[plan.id] = plan;
    persist(db);
    return plan;
  },
  updatePlan(planId, patch) {
    const plan = db.plans[planId];
    if (!plan) return null;
    Object.assign(plan, patch, { updatedAt: new Date().toISOString() });
    persist(db);
    return plan;
  },

  getInviteByToken(t) {
    return db.invites[t] || null;
  },
  listInvites(planId) {
    return Object.values(db.invites).filter((i) => i.planId === planId);
  },
  createInvite(invite) {
    db.invites[invite.token] = invite;
    persist(db);
    return invite;
  },
  updateInvite(inviteId, planId, patch) {
    const invite = Object.values(db.invites).find(
      (i) => i.id === inviteId && i.planId === planId
    );
    if (!invite) return null;
    Object.assign(invite, patch);
    persist(db);
    return invite;
  },

  list(collection, planId) {
    return db[collection][planId] || [];
  },
  create(collection, planId, item) {
    if (!db[collection][planId]) db[collection][planId] = [];
    db[collection][planId].push(item);
    persist(db);
    return item;
  },
  update(collection, planId, itemId, patch) {
    const items = db[collection][planId] || [];
    const item = items.find((i) => i.id === itemId);
    if (!item) return null;
    Object.assign(item, patch, { updatedAt: new Date().toISOString() });
    persist(db);
    return item;
  },
  remove(collection, planId, itemId) {
    const items = db[collection][planId] || [];
    const index = items.findIndex((i) => i.id === itemId);
    if (index === -1) return false;
    items.splice(index, 1);
    persist(db);
    return true;
  },
};

export { COLLECTIONS };
