import { useEffect, useState } from "react";

// Owner-only: this is the one screen that names people rather than party
// details, and the only place new invite links get minted or cut off.
export default function CollaboratorsTab({ api, currentToken }) {
  const [invites, setInvites] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [name, setName] = useState("");
  const [role, setRole] = useState("collaborator");
  const [copiedId, setCopiedId] = useState(null);

  const baseUrl = window.location.origin;

  async function refresh() {
    setLoading(true);
    try {
      const data = await api.listInvites(baseUrl);
      setInvites(data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleCreate(e) {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      await api.createInvite(name.trim(), role, baseUrl);
      setName("");
      setRole("collaborator");
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  async function toggleRevoked(invite) {
    if (isYou(invite)) {
      window.alert(
        "You can't revoke your own link from inside the app — that would lock you out immediately. Have another owner revoke it, or use a different owner link."
      );
      return;
    }
    try {
      await api.setInviteRevoked(invite.id, !invite.revoked, baseUrl);
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  function isYou(invite) {
    return invite.link.endsWith(`/p/${currentToken}`);
  }

  async function copy(invite) {
    try {
      await navigator.clipboard.writeText(invite.link);
      setCopiedId(invite.id);
      setTimeout(() => setCopiedId(null), 1500);
    } catch {
      window.prompt("Copy this link:", invite.link);
    }
  }

  return (
    <section className="tab-panel">
      <header className="tab-panel-header">
        <div>
          <h2>Collaborators</h2>
          <p className="tab-blurb">
            Give each helper their own link. Nobody else can find this planner — a link is the
            only way in, so only send it to people you actually want in.
          </p>
        </div>
      </header>

      <form className="record-form invite-form" onSubmit={handleCreate}>
        <div className="record-form-grid">
          <label className="field">
            <span>Name</span>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Sarah" />
          </label>
          <label className="field field-small">
            <span>Role</span>
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="collaborator">Collaborator</option>
              <option value="owner">Owner (can also manage invites)</option>
            </select>
          </label>
        </div>
        <div className="record-form-actions">
          <button type="submit" className="btn btn-primary">
            Generate invite link
          </button>
        </div>
      </form>

      {error && <p className="error-text">{error}</p>}
      {loading && <p className="muted">Loading…</p>}

      <ul className="record-list">
        {invites.map((invite) => {
          const you = isYou(invite);
          return (
            <li key={invite.id} className={`record-card invite-card ${invite.revoked ? "revoked" : ""}`}>
              <div className="record-fields">
                <div className="record-field">
                  <span className="record-field-label">Name</span>
                  <span className="record-field-value">
                    {invite.name}
                    {you && <span className="you-badge">You</span>}
                  </span>
                </div>
                <div className="record-field">
                  <span className="record-field-label">Role</span>
                  <span className="record-field-value">{invite.role}</span>
                </div>
                <div className="record-field record-field-full">
                  <span className="record-field-label">Link</span>
                  <span className="record-field-value link-value">
                    {invite.revoked ? "revoked" : invite.link}
                  </span>
                </div>
              </div>
              <div className="record-card-actions">
                {!invite.revoked && (
                  <button className="btn btn-ghost" onClick={() => copy(invite)}>
                    {copiedId === invite.id ? "Copied!" : "Copy link"}
                  </button>
                )}
                <button
                  className="btn btn-ghost btn-danger"
                  onClick={() => toggleRevoked(invite)}
                  disabled={you && !invite.revoked}
                  title={you && !invite.revoked ? "You can't revoke the link you're using right now" : undefined}
                >
                  {invite.revoked ? "Restore" : "Revoke"}
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
