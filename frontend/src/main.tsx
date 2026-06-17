import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'react-hot-toast'
import './index.css'

import { LoginPage }          from './pages/LoginPage'
import { ChangePasswordPage } from './pages/ChangePasswordPage'
import { DashboardPage }      from './pages/DashboardPage'
import { ConnectorsPage }     from './pages/ConnectorsPage'
import { AccessControlPage }  from './pages/AccessControlPage'
import { PeoplePage }         from './pages/PeoplePage'
import { MCPPage }            from './pages/MCPPage'
import { TeamAccessPage }     from './pages/TeamAccessPage'
import { Layout }             from './components/Layout'
import { ProtectedRoute }     from './components/ProtectedRoute'


const qc = new QueryClient()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes>
          <Route path="/login"          element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/change-password" element={<ChangePasswordPage />} />
            <Route element={<Layout />}>
              <Route path="/"            element={<DashboardPage />} />
              <Route path="/connectors"  element={<ConnectorsPage />} />
              <Route path="/connectors/:connectorId/team-access" element={<TeamAccessPage />} />
              <Route path="/access"      element={<AccessControlPage />} />
              <Route path="/people"      element={<PeoplePage />} />
              <Route path="/mcp"         element={<MCPPage />} />
              <Route path="/query"       element={<Navigate to="/mcp" replace />} />
              {/* Legacy redirects */}
              <Route path="/permissions" element={<Navigate to="/access?tab=connector" replace />} />
              <Route path="/rls"         element={<Navigate to="/access?tab=rls" replace />} />
              <Route path="/packages"    element={<Navigate to="/access?tab=packages" replace />} />
              <Route path="/users"       element={<Navigate to="/people?tab=users" replace />} />
              <Route path="/departments" element={<Navigate to="/people?tab=departments" replace />} />
              <Route path="/roles"       element={<Navigate to="/people?tab=roles" replace />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="top-right" />
    </QueryClientProvider>
  </React.StrictMode>
)
