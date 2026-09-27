import { useState } from "react";

const FIELDS = [
  { name: "title", label: "Event name", type: "text" },
  { name: "eventDate", label: "Date", type: "date" },
  { name: "startTime", label: "Start time", type: "text", placeholder: "16:00" },
  { name: "endTime", label: "End time", type: "text", placeholder: "22:00" },
  { name: "address", label: "Location", type: "text" },
  { name: "hosts", label: "Hosted by", type: "text" },
  { name: "guestsOfHonour", label: "Guest(s) of honour", type: "text" },
  { name: "expectedGuestCount", label: "Expected guests", type: "number" },
  { name: "theme", label: "Theme / vibe", type: "text", placeholder: "Warm lanterns, vintage glass..." },
];

export default function OverviewTab({ api, plan, onPlanChange }) {
  const [values, setValues] = useState(() => ({ ...plan }));
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState(null);
  const [error, setError] = useState(null);

  function setField(name, value) {
    setValues((prev) => ({ ...prev, [name]: value }));
  }

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    try {
      const updated = await api.updatePlan(values);
      onPlanChange(updated);
      setSavedAt(new Date());
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  const daysToGo = plan.eventDate
    ? Math.ceil((new Date(plan.eventDate) - new Date()) / (1000 * 60 * 60 * 24))
    : null;

  return (
    <section className="tab-panel">
      <header className="tab-panel-header">
        <div>
          <h2>Overview</h2>
          <p className="tab-blurb">The basics everyone preparing this needs to know.</p>
        </div>
        {daysToGo !== null && daysToGo >= 0 && (
          <div className="countdown-badge">{daysToGo === 0 ? "Today!" : `${daysToGo} days to go`}</div>
        )}
      </header>

      <form className="record-form overview-form" onSubmit={save}>
        <div className="record-form-grid">
          {FIELDS.map((field) => (
            <label key={field.name} className="field">
              <span>{field.label}</span>
              <input
                type={field.type}
                placeholder={field.placeholder}
                value={values[field.name] ?? ""}
                onChange={(e) => setField(field.name, e.target.value)}
              />
            </label>
          ))}
        </div>

        <label className="field field-full">
          <span>Notes (whatever doesn't fit elsewhere)</span>
          <textarea
            rows={5}
            value={values.notes ?? ""}
            onChange={(e) => setField("notes", e.target.value)}
          />
        </label>

        {error && <p className="error-text">{error}</p>}
        <div className="record-form-actions">
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </button>
          {savedAt && !error && <span className="muted">Saved</span>}
        </div>
      </form>
    </section>
  );
}
