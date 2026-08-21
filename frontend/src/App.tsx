import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { AppShell } from "./components/AppShell";
import { AuthPage } from "./pages/AuthPage";
import { NoteSubmitPage } from "./pages/NoteSubmitPage";
import { AnalysisPage } from "./pages/AnalysisPage";
import { HistoryPage } from "./pages/HistoryPage";

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<AuthPage />} />
        <Route element={<AppShell />}>
          <Route path="/" element={<NoteSubmitPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/notes/:noteId/analyses/:analysisId" element={<AnalysisPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}
