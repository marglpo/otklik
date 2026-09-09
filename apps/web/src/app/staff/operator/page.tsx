import { ProtectedStaffPage } from "@/components/auth/protected-staff-page"

export default function OperatorPlaceholderPage() {
  return <ProtectedStaffPage requiredRole="operator" title="Operator workspace" />
}
