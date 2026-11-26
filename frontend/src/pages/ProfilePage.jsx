import { useState } from "react";
import { ChevronRight, KeyRound, UserRound } from "lucide-react";
import { Button } from "../components/ui/button.jsx";
import { changePassword, updateProfile } from "../services/api.js";

export default function ProfilePage({ user, onProfileUpdated, onPasswordChanged }) {
  const [fullName, setFullName] = useState(user.full_name);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [passwordChanged, setPasswordChanged] = useState(false);

  async function saveProfile(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const updated = await updateProfile({ full_name: fullName });
      onProfileUpdated(updated);
      setFullName(updated.full_name);
      setNotice("Profile updated.");
    } catch (caught) {
      setError(caught.message);
    } finally {
      setBusy(false);
    }
  }

  async function savePassword(event) {
    event.preventDefault();
    if (newPassword !== confirmPassword) {
      setError("The new passwords do not match.");
      return;
    }
    if (currentPassword === newPassword) {
      setError("Choose a password different from your current password.");
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await changePassword({ currentPassword, newPassword });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setNotice(result.message);
      setPasswordChanged(true);
    } catch (caught) {
      setError(caught.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="placeholder-page account-page">
      <div className="page-heading-row">
        <div><div className="page-breadcrumb"><span>Account</span><ChevronRight size={13} /><strong>Profile</strong></div><h1>Profile</h1><p className="page-description">Update your account details and password.</p></div>
      </div>
      {error && <div className="stage-error" role="alert">{error}</div>}
      {notice && <div className="workspace-notice" role="status">{notice}</div>}
      <section className="stage-panel account-panel">
        <div className="stage-toolbar"><div><strong><UserRound size={14} /> Personal details</strong><span>Used to identify you in project activity.</span></div></div>
        <form className="project-form" onSubmit={saveProfile}>
          <label>Full name<input required minLength={1} maxLength={120} value={fullName} onChange={(event) => setFullName(event.target.value)} /></label>
          <label>Email<input type="email" value={user.email} disabled /><small>Email address changes and verification are not available yet.</small></label>
          <div className="account-verification">Email status: {user.is_verified ? "Verified" : "Not verified"}</div>
          <div className="project-form-actions"><Button type="submit" disabled={busy || fullName.trim() === user.full_name}>{busy ? "Saving…" : "Save profile"}</Button></div>
        </form>
      </section>
      <section className="stage-panel account-panel">
        <div className="stage-toolbar"><div><strong><KeyRound size={14} /> Change password</strong><span>Changing your password signs out all active sessions.</span></div></div>
        <form className="project-form account-password-form" onSubmit={savePassword}>
          <label>Current password<input type="password" autoComplete="current-password" required maxLength={128} value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} /></label>
          <label>New password<input type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} /><small>Use at least 12 characters.</small></label>
          <label>Confirm new password<input type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} /></label>
          <div className="project-form-actions"><Button type="submit" disabled={busy || passwordChanged}>{busy ? "Updating…" : "Change password"}</Button>{passwordChanged && <Button type="button" variant="outline" onClick={onPasswordChanged}>Sign in again</Button>}</div>
        </form>
      </section>
    </div>
  );
}
