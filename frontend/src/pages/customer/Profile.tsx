import { AppShell } from "../../components/AppShell";
import { Account } from "../../components/Account";
import { Heading } from "../../components/Product";

export default function Profile() {
  return (
    <AppShell variant="customer">
      <Heading
        title="Your profile"
        body="Manage your account information and session."
      />
      <div className="mt-6 max-w-2xl">
        <Account />
      </div>
    </AppShell>
  );
}
