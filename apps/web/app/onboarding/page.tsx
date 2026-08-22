import { redirect } from "next/navigation";
import { auth } from "../../auth";
import { createWorkspace } from "./actions";
import OnboardingWizard from "./wizard";

export default async function OnboardingPage() {
  const session = await auth();
  if (!session?.user?.id) redirect("/login?callbackUrl=/onboarding");
  return <OnboardingWizard action={createWorkspace}/>;
}
