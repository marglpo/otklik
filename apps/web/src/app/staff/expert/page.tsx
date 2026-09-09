import { ProtectedStaffPage } from "@/components/auth/protected-staff-page"

export default function ExpertPlaceholderPage() {
  return <ProtectedStaffPage requiredRole="expert" title="Expert workspace" />
}
