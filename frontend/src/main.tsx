import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'react-hot-toast'
import './index.css'

import { LoginPage }       from './pages/LoginPage'
import { RegisterPage }    from './pages/RegisterPage'
import { DashboardPage }   from './pages/DashboardPage'
import { ConnectorsPage }  from './pages/ConnectorsPage'
import { PermissionsPage } from './pages/PermissionsPage'
import { QueryPage }       from './pages/QueryPage'
import { UsersPage }       from './pages/UsersPage'
import { MCPPage }         from './pages/MCPPage'
import { Layout }          from './components/Layout'
import { ProtectedRoute }  from './components/ProtectedRoute'

const qc = new QueryClient()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes>
          <Route path="/login"    element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              <Route path="/"            element={<DashboardPage />} />
              <Route path="/connectors"  element={<ConnectorsPage />} />
              <Route path="/permissions" element={<PermissionsPage />} />
              <Route path="/query"       element={<QueryPage />} />
              <Route path="/mcp"         element={<MCPPage />} />
              <Route path="/users"       element={<UsersPage />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="top-right" />
    </QueryClientProvider>
  </React.StrictMode>
)
