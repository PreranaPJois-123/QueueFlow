import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { ToastProvider } from "./components/Toast";
import { AuthProvider, RequireAuth } from "./lib/auth";
import { RealtimeProvider } from "./lib/realtime";

import Landing from "./pages/Landing";
import Login from "./pages/auth/Login";
import Register from "./pages/auth/Register";
import { ForgotPassword, ResetPassword } from "./pages/auth/PasswordReset";
import VenueList from "./pages/explore/VenueList";
import VenueDetail from "./pages/explore/VenueDetail";
import BookAppointment from "./pages/explore/BookAppointment";
import MyBookings from "./pages/bookings/MyBookings";
import BookingDetail from "./pages/bookings/BookingDetail";
import ReservationDetail from "./pages/bookings/ReservationDetail";
import Notifications from "./pages/Notifications";
import CustomerDashboard from "./pages/customer/Dashboard";
import Profile from "./pages/customer/Profile";
import Services from "./pages/customer/Services";
import MyTicket from "./pages/customer/MyTicket";
import Appointments from "./pages/customer/Appointments";
import { OpsVenueBoard, OpsVenueList } from "./pages/ops/VenueOps";
import AdminVenues from "./pages/admin/AdminVenues";
import AdminVenueEditor from "./pages/admin/AdminVenueEditor";
import { AdminKnowledge, AdminUsers } from "./pages/admin/AdminPeople";

import StaffDashboard from "./pages/staff/Dashboard";
import StaffQueues from "./pages/staff/Queues";
import StaffQueueDetail from "./pages/staff/QueueDetail";
import StaffCustomers from "./pages/staff/Customers";
import StaffAppointments from "./pages/staff/Appointments";
import StaffAnalytics from "./pages/staff/Analytics";
import StaffSettings from "./pages/staff/Settings";

const STAFF = ["STAFF", "ADMIN"] as const;
const signedIn = (el: React.ReactNode) => <RequireAuth>{el}</RequireAuth>;
const staff = (el: React.ReactNode) => <RequireAuth roles={[...STAFF]}>{el}</RequireAuth>;
const admin = (el: React.ReactNode) => <RequireAuth roles={["ADMIN"]}>{el}</RequireAuth>;

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />

      <Route path="/hospitals" element={<VenueList kind="HOSPITAL" />} />
      <Route path="/shops" element={<VenueList kind="SHOP" />} />
      <Route path="/hotels" element={<VenueList kind="HOTEL" />} />
      <Route path="/venues/:id" element={<VenueDetail />} />
      <Route path="/venues/:id/book" element={signedIn(<BookAppointment />)} />

      <Route path="/dashboard" element={signedIn(<CustomerDashboard />)} />
      <Route path="/bookings" element={signedIn(<MyBookings />)} />
      <Route path="/bookings/:reference" element={signedIn(<BookingDetail />)} />
      <Route path="/reservations/:reference" element={signedIn(<ReservationDetail />)} />
      <Route path="/notifications" element={signedIn(<Notifications />)} />
      <Route path="/profile" element={signedIn(<Profile />)} />

      <Route path="/services" element={signedIn(<Services />)} />
      <Route path="/join-queue" element={signedIn(<Services />)} />
      <Route path="/my-ticket" element={signedIn(<MyTicket />)} />
      <Route path="/appointments" element={signedIn(<Appointments />)} />

      <Route path="/staff/venues" element={staff(<OpsVenueList />)} />
      <Route path="/staff/venues/:id" element={staff(<OpsVenueBoard />)} />
      <Route path="/staff/dashboard" element={staff(<StaffDashboard />)} />
      <Route path="/staff/queues" element={staff(<StaffQueues />)} />
      <Route path="/staff/queue/:id" element={staff(<StaffQueueDetail />)} />
      <Route path="/staff/customers" element={staff(<StaffCustomers />)} />
      <Route path="/staff/appointments" element={staff(<StaffAppointments />)} />
      <Route path="/staff/analytics" element={staff(<StaffAnalytics />)} />
      <Route path="/staff/settings" element={staff(<StaffSettings />)} />

      <Route path="/admin/venues" element={admin(<AdminVenues />)} />
      <Route path="/admin/venues/:id" element={admin(<AdminVenueEditor />)} />
      <Route path="/admin/users" element={admin(<AdminUsers />)} />
      <Route path="/admin/knowledge" element={admin(<AdminKnowledge />)} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <AuthProvider>
          <RealtimeProvider>
            <AppRoutes />
          </RealtimeProvider>
        </AuthProvider>
      </ToastProvider>
    </BrowserRouter>
  );
}
