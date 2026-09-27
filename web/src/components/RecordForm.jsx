import { useState } from "react";

function initialValues(fields, record) {
  const values = {};
  for (const field of fields) {
    if (field.type === "checkbox") values[field.name] = !!record?.[field.name];
    else values[field.name] = record?.[field.name] ?? "";
  }
  return values;
}

export default function RecordForm({ fields, record, onSubmit, onCancel, submitLabel }) {
  const [values, setValues] = useState(() => initialValues(fields, record));
  const [saving, setSaving] = useState(false);

  function setField(name, value) {
    setValues((prev) => ({ ...prev, [name]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setSaving(true);
    try {
      await onSubmit(values);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="record-form" onSubmit={handleSubmit}>
      <div className="record-form-grid">
        {fields.map((field) => (
          <label key={field.name} className={`field field-${field.width || "regular"}`}>
            <span>{field.label}</span>
            {field.type === "textarea" && (
              <textarea
                value={values[field.name]}
                onChange={(e) => setField(field.name, e.target.value)}
                rows={2}
              />
            )}
            {field.type === "select" && (
              <select
                value={values[field.name]}
                onChange={(e) => setField(field.name, e.target.value)}
              >
                <option value="">—</option>
                {field.options.map((opt) => (
                  <option key={opt} value={opt}>
                    {opt}
                  </option>
                ))}
              </select>
            )}
            {field.type === "checkbox" && (
              <input
                type="checkbox"
                checked={values[field.name]}
                onChange={(e) => setField(field.name, e.target.checked)}
              />
            )}
            {["text", "number", "date"].includes(field.type) && (
              <input
                type={field.type}
                placeholder={field.placeholder}
                value={values[field.name]}
                onChange={(e) => setField(field.name, e.target.value)}
              />
            )}
          </label>
        ))}
      </div>
      <div className="record-form-actions">
        <button type="submit" className="btn btn-primary" disabled={saving}>
          {saving ? "Saving…" : submitLabel}
        </button>
        {onCancel && (
          <button type="button" className="btn btn-ghost" onClick={onCancel}>
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}
