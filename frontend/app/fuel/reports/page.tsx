import { redirect } from "next/navigation";

export default function FuelReportsPage() {
  redirect("/analytics?view=journal");
}

