import { Routes, Route } from "react-router-dom";
import PlannerPage from "./pages/PlannerPage.jsx";

// URBOS itself has no home page worth speaking of here — this whole app
// is one hidden feature. The only real route is /p/:token; anything else,
// including "/", renders nothing that hints at what this is.
export default function App() {
  return (
    <Routes>
      <Route path="/p/:inviteToken" element={<PlannerPage />} />
      <Route path="*" element={<div />} />
    </Routes>
  );
}
