import { store, id, token } from "./store.js";

// The only way a plan comes into existence: run this once from a terminal
// you already trust. There is no "create plan" button in the app, because
// the whole point of this feature is that it isn't discoverable — you
// provision it yourself and hand out invite links from there.
function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg.startsWith("--")) {
      const key = arg.slice(2);
      const value = argv[i + 1] && !argv[i + 1].startsWith("--") ? argv[i + 1] : "true";
      args[key] = value;
      if (value !== "true") i += 1;
    }
  }
  return args;
}

const args = parseArgs(process.argv.slice(2));
const baseUrl = args["base-url"] || process.env.URBOS_WEB_BASE_URL || "http://localhost:5173";
const ownerName = args["owner-name"] || "Owner";

const plan = store.createPlan({
  id: id(),
  title: args.title || "Untitled celebration",
  eventDate: args.date || "",
  startTime: args.start || "",
  endTime: args.end || "",
  address: args.address || "",
  hosts: args.hosts || "",
  guestsOfHonour: args["guests-of-honour"] || "",
  expectedGuestCount: args["guest-count"] ? Number(args["guest-count"]) : null,
  theme: args.theme || "",
  notes: "",
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
});

const ownerInvite = store.createInvite({
  id: id(),
  planId: plan.id,
  token: token(),
  name: ownerName,
  role: "owner",
  revoked: false,
  createdAt: new Date().toISOString(),
});

console.log("Created plan:", plan.title || "(untitled)");
console.log("Owner invite link (keep this one to yourself, or share carefully — it manages every other invite):");
console.log(`  ${baseUrl}/p/${ownerInvite.token}`);
console.log("\nOpen the link, then use the Collaborators tab to generate a separate link per helper.");
