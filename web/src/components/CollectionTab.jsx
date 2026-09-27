import { useEffect, useState } from "react";
import RecordForm from "./RecordForm.jsx";

export default function CollectionTab({ api, tab }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState(null);

  async function refresh() {
    setLoading(true);
    try {
      const data = await api.list(tab.key);
      const sorted = tab.sortBy
        ? [...data].sort((a, b) => (a[tab.sortBy] || "").localeCompare(b[tab.sortBy] || ""))
        : data;
      setItems(sorted);
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
  }, [tab.key]);

  async function handleAdd(values) {
    try {
      await api.create(tab.key, values);
      setAdding(false);
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleEdit(id, values) {
    try {
      await api.update(tab.key, id, values);
      setEditingId(null);
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDelete(id) {
    if (!window.confirm("Remove this item?")) return;
    try {
      await api.remove(tab.key, id);
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section className="tab-panel">
      <header className="tab-panel-header">
        <div>
          <h2>{tab.label}</h2>
          <p className="tab-blurb">{tab.blurb}</p>
        </div>
        {!adding && (
          <button className="btn btn-primary" onClick={() => setAdding(true)}>
            + Add
          </button>
        )}
      </header>

      {adding && (
        <div className="record-card record-card-new">
          <RecordForm fields={tab.fields} onSubmit={handleAdd} onCancel={() => setAdding(false)} submitLabel="Add" />
        </div>
      )}

      {tab.summary && items.length > 0 && (
        <div className="summary-strip">
          {tab.summary(items).map((s) => (
            <div key={s.label} className="summary-item">
              <span className="summary-value">{s.value}</span>
              <span className="summary-label">{s.label}</span>
            </div>
          ))}
        </div>
      )}

      {error && <p className="error-text">{error}</p>}
      {loading && <p className="muted">Loading…</p>}

      {!loading && items.length === 0 && !adding && (
        <p className="muted">Nothing here yet.</p>
      )}

      <ul className="record-list">
        {items.map((item) => (
          <li key={item.id} className="record-card">
            {editingId === item.id ? (
              <RecordForm
                fields={tab.fields}
                record={item}
                onSubmit={(values) => handleEdit(item.id, values)}
                onCancel={() => setEditingId(null)}
                submitLabel="Save"
              />
            ) : (
              <>
                <div className="record-fields">
                  {tab.fields.map((field) => {
                    const value = item[field.name];
                    if (value === undefined || value === "" || value === null) return null;
                    if (field.type === "checkbox" && !value) return null;
                    return (
                      <div key={field.name} className="record-field">
                        <span className="record-field-label">{field.label}</span>
                        <span className="record-field-value">
                          {field.type === "checkbox" ? "✓" : String(value)}
                        </span>
                      </div>
                    );
                  })}
                </div>
                <div className="record-card-actions">
                  <button className="btn btn-ghost" onClick={() => setEditingId(item.id)}>
                    Edit
                  </button>
                  <button className="btn btn-ghost btn-danger" onClick={() => handleDelete(item.id)}>
                    Delete
                  </button>
                </div>
              </>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
