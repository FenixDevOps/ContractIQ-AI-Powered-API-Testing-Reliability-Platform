import { useState } from "react";
import { Activity, ArrowLeft, ArrowRight, KeyRound, LockKeyhole, Mail, UserRound } from "lucide-react";
import { Button } from "../components/ui/button.jsx";
import {
  confirmPasswordReset,
  confirmEmailVerification,
  createAccount,
  login,
  requestEmailVerification,
  requestPasswordReset,
} from "../services/api.js";

const TITLES = {
  login: "Welcome back",
  register: "Create your account",
  forgot: "Reset your password",
  reset: "Choose a new password",
  verify: "Verify your email",
};

export default function AuthPage({ mode, resetToken, verificationToken, onModeChange, onAuthenticated }) {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (mode === "login") {
        onAuthenticated(await login({ email, password }));
      } else if (mode === "register") {
        const result = await createAccount({ full_name: fullName, email, password });
        if (result.access_token) {
          onAuthenticated(result);
        } else {
          setNotice(result.message);
          onModeChange("verify");
        }
      } else if (mode === "forgot") {
        const result = await requestPasswordReset(email);
        setNotice(result.message);
      } else if (mode === "verify") {
        if (verificationToken) {
          const result = await confirmEmailVerification(verificationToken);
          setNotice(result.message);
          onModeChange("login");
        } else {
          const result = await requestEmailVerification(email);
          setNotice(result.message);
        }
      } else {
        if (password !== confirmPassword) {
          setError("The passwords do not match.");
          return;
        }
        const result = await confirmPasswordReset(resetToken, password);
        setNotice(result.message);
        onModeChange("login");
      }
    } catch (caught) {
      setError(caught.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="auth-title">
        <a className="auth-brand" href="/" aria-label="ContractIQ home">
          <span className="brand-mark" aria-hidden="true"><Activity size={18} /></span>
          <span>Contract<span className="brand-accent">IQ</span></span>
        </a>
        <div className="auth-heading">
          <span className="section-overline">API RELIABILITY WORKSPACE</span>
          <h1 id="auth-title">{TITLES[mode]}</h1>
          <p>
            {mode === "register" && "Create an account to manage your API projects and team."}
            {mode === "login" && "Sign in to continue to your ContractIQ workspace."}
            {mode === "forgot" && "Enter your account email and we’ll send reset instructions if it matches an account."}
            {mode === "reset" && "Set a new password for your ContractIQ account."}
            {mode === "verify" && (verificationToken
              ? "Confirm your email address to activate your account."
              : "Enter your account email and we’ll send a new verification link if needed.")}
          </p>
        </div>
        <form className="auth-form" onSubmit={submit}>
          {mode === "register" && (
            <label>
              Full name
              <span className="auth-input-wrap"><UserRound size={15} /><input autoComplete="name" required maxLength={120} value={fullName} onChange={(event) => setFullName(event.target.value)} /></span>
            </label>
          )}
          {(["login", "register", "forgot"].includes(mode) || (mode === "verify" && !verificationToken)) && (
            <label>
              Email
              <span className="auth-input-wrap"><Mail size={15} /><input type="email" autoComplete="email" required maxLength={320} value={email} onChange={(event) => setEmail(event.target.value)} /></span>
            </label>
          )}
          {["login", "register", "reset"].includes(mode) && (
            <label>
              {mode === "reset" ? "New password" : "Password"}
              <span className="auth-input-wrap"><LockKeyhole size={15} /><input type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} required minLength={12} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} /></span>
              {mode !== "login" && <small>Use at least 12 characters.</small>}
            </label>
          )}
          {mode === "reset" && (
            <label>
              Confirm password
              <span className="auth-input-wrap"><KeyRound size={15} /><input type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} /></span>
            </label>
          )}
          {error && <div className="stage-error" role="alert">{error}</div>}
          {notice && <div className="auth-notice" role="status">{notice}</div>}
          <Button className="auth-submit" type="submit" disabled={busy || (mode === "reset" && !resetToken)}>
            {busy
              ? "Please wait…"
              : mode === "forgot"
                ? "Send reset instructions"
                : mode === "reset"
                  ? "Update password"
                  : mode === "verify"
                    ? verificationToken ? "Verify email" : "Send verification email"
                    : mode === "register" ? "Create account" : "Sign in"}
            {!busy && <ArrowRight size={15} />}
          </Button>
        </form>
        <div className="auth-links">
          {mode === "login" && <>
            <button type="button" onClick={() => onModeChange("forgot")}>Forgot password?</button>
            <span>New to ContractIQ? <button type="button" onClick={() => onModeChange("register")}>Create account</button></span>
          </>}
          {mode === "register" && <span>Already have an account? <button type="button" onClick={() => onModeChange("login")}>Sign in</button></span>}
          {mode === "forgot" && <button type="button" onClick={() => onModeChange("login")}><ArrowLeft size={13} /> Back to sign in</button>}
          {mode === "reset" && <button type="button" onClick={() => onModeChange("login")}><ArrowLeft size={13} /> Back to sign in</button>}
          {mode === "verify" && <button type="button" onClick={() => onModeChange("login")}><ArrowLeft size={13} /> Back to sign in</button>}
          {mode === "login" && <button type="button" onClick={() => onModeChange("verify")}>Resend verification email</button>}
        </div>
        {mode === "reset" && !resetToken && <div className="stage-error" role="alert">This reset link is missing or invalid. Request a new one.</div>}
      </section>
      <p className="auth-footnote">ContractIQ · Secure API quality and reliability</p>
    </main>
  );
}
