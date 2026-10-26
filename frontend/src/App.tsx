import { lazy, Suspense } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { LandingPage } from './pages/LandingPage'

const LoginPage = lazy(() =>
  import('./pages/LoginPage').then((module) => ({ default: module.LoginPage })),
)
const ForgotPasswordPage = lazy(() =>
  import('./pages/PasswordPages').then((module) => ({ default: module.ForgotPasswordPage })),
)
const ResetPasswordPage = lazy(() =>
  import('./pages/PasswordPages').then((module) => ({ default: module.ResetPasswordPage })),
)
const WorkspaceHome = lazy(() =>
  import('./WorkspaceHome').then((module) => ({ default: module.WorkspaceHome })),
)

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<p className="boot">Loading…</p>}>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/app/*" element={<WorkspaceHome />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}
