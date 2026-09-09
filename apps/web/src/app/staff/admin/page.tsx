import { ProtectedStaffPage } from "@/components/auth/protected-staff-page"

export default function AdminPlaceholderPage() {
  return <ProtectedStaffPage requiredRole="admin" title="Administration" />
}
