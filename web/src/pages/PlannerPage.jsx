import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { createApiClient, rememberToken, ApiError } from "../api/client.js";
import { TABS } from "../config/tabs.js";
import OverviewTab from "../components/OverviewTab.jsx";
import CollectionTab from "../components/CollectionTab.jsx";
import CollaboratorsTab from "../components/CollaboratorsTab.jsx";

const REVOKED_MESSAGE =
  "This link isn't valid — it may have been revoked. Ask whoever shared it for a fresh one.";

export default function PlannerPage() {
  const { inviteToken } = useParams();
  const [state, setState] = useState({ status: "loading", plan: null, me: null, error: null });

  const api = useMemo(
    () =>
      createApiClient(inviteToken, {
        onUnauthorized: () =>
          setState({ status: "error", plan: null, me: null, error: REVOKED_MESSAGE }),
      }),
    [inviteToken]
  );

  const [activeTab, setActiveTab] = useState("overview");

  useEffect(() => {
    rememberToken(inviteToken);
    api
      .getMe()
      .then(({ plan, me }) => setState({ status: "ready", plan, me, error: null }))
      .catch((err) => {
        const message =
          err instanceof ApiError && err.status === 401 ? REVOKED_MESSAGE : "Couldn't load the planner right now.";
        setState({ status: "error", plan: null, me: null, error: message });
      });
  }, [api, inviteToken]);

  if (state.status === "loading") {
    return <div className="planner-shell centered">Loading…</div>;
  }

  if (state.status === "error") {
    return (
      <div className="planner-shell centered">
        <p className="error-text">{state.error}</p>
      </div>
    );
  }

  const { plan, me } = state;

  function handlePlanChange(updated) {
    setState((prev) => ({ ...prev, plan: updated }));
  }

  return (
    <div className="planner-shell">
      <header className="planner-header">
        <div>
          <p className="planner-kicker">URBOS · celebrations</p>
          <h1>{plan.title || "Untitled celebration"}</h1>
        </div>
        <div className="planner-identity">
          Viewing as <strong>{me.name}</strong> · {me.role}
        </div>
      </header>

      <nav className="tab-nav">
        <button
          className={activeTab === "overview" ? "active" : ""}
          onClick={() => setActiveTab("overview")}
        >
          Overview
        </button>
        {TABS.map((tab) => (
          <button
            key={tab.key}
            className={activeTab === tab.key ? "active" : ""}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
        {me.role === "owner" && (
          <button
            className={activeTab === "collaborators" ? "active" : ""}
            onClick={() => setActiveTab("collaborators")}
          >
            Collaborators
          </button>
        )}
      </nav>

      <main className="tab-content">
        {activeTab === "overview" && (
          <OverviewTab api={api} plan={plan} onPlanChange={handlePlanChange} />
        )}
        {TABS.map(
          (tab) => activeTab === tab.key && <CollectionTab key={tab.key} api={api} tab={tab} />
        )}
        {activeTab === "collaborators" && me.role === "owner" && (
          <CollaboratorsTab api={api} currentToken={inviteToken} />
        )}
      </main>
    </div>
  );
}
