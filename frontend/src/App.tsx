import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, RequireAuth } from './lib/auth'
import { ToastProvider } from './components/Toast'

import Landing from './pages/Landing'
import Login from './pages/Login'
import Register from './pages/Register'

import CustomerDashboard from './pages/customer/Dashboard'
import Services from './pages/customer/Services'
import MyTicket from './pages/customer/MyTicket'
import Appointments from './pages/customer/Appointments'
import Profile from './pages/customer/Profile'

import StaffDashboard from './pages/staff/Dashboard'
import StaffQueues from './pages/staff/Queues'
import StaffQueueDetail from './pages/staff/QueueDetail'
import StaffCustomers from './pages/staff/Customers'
import StaffAnalytics from './pages/staff/Analytics'
import StaffSettings from './pages/staff/Settings'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />

            <Route path="/dashboard" element={<RequireAuth roles={['CUSTOMER']}><CustomerDashboard /></RequireAuth>} />
            <Route path="/services" element={<RequireAuth roles={['CUSTOMER']}><Services /></RequireAuth>} />
            <Route path="/join-queue" element={<RequireAuth roles={['CUSTOMER']}><Services /></RequireAuth>} />
            <Route path="/my-ticket" element={<RequireAuth roles={['CUSTOMER']}><MyTicket /></RequireAuth>} />
            <Route path="/appointments" element={<RequireAuth roles={['CUSTOMER']}><Appointments /></RequireAuth>} />
            <Route path="/profile" element={<RequireAuth roles={['CUSTOMER']}><Profile /></RequireAuth>} />

            <Route path="/staff/dashboard" element={<RequireAuth roles={['STAFF', 'ADMIN']}><StaffDashboard /></RequireAuth>} />
            <Route path="/staff/queues" element={<RequireAuth roles={['STAFF', 'ADMIN']}><StaffQueues /></RequireAuth>} />
            <Route path="/staff/queue/:id" element={<RequireAuth roles={['STAFF', 'ADMIN']}><StaffQueueDetail /></RequireAuth>} />
            <Route path="/staff/customers" element={<RequireAuth roles={['STAFF', 'ADMIN']}><StaffCustomers /></RequireAuth>} />
            <Route path="/staff/analytics" element={<RequireAuth roles={['STAFF', 'ADMIN']}><StaffAnalytics /></RequireAuth>} />
            <Route path="/staff/settings" element={<RequireAuth roles={['STAFF', 'ADMIN']}><StaffSettings /></RequireAuth>} />

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
