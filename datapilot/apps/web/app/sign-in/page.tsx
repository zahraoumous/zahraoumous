"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import Icon from "../components/glyph";
import { useI18n, PreferenceControls } from "../lib/i18n";
import { api, errorMessage } from "../lib/api";

export default function SignIn() {
  const router = useRouter();
  const {t} = useI18n();
  const [register, setRegister] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const form = new FormData(event.currentTarget);
    try {
      await api(`/auth/${register ? "register" : "login"}`, { method: "POST", body: JSON.stringify({ email: String(form.get("email") || ""), password: String(form.get("password") || ""), ...(register ? { display_name: String(form.get("name") || "") } : {}) }) });
      router.push("/app"); router.refresh();
    } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }
  return <div className="auth-page">
    <aside className="auth-story"><Link className="brand" href="/"><span className="brand-mark"><Icon name="layers" size={25}/></span>DataPilot<span className="brand-tag">AI</span></Link>
      <div className="auth-story-copy"><h1>{t("A clearer home for your data.")}</h1><p>{t("A focused workspace for turning scattered spreadsheets into clear, dependable data.")}</p>
        <div className="auth-story-features"><span><Icon name="folder"/>{t("Multiple files. One workspace.")}</span><span><Icon name="shield"/>{t("Quality checks with actual evidence.")}</span><span><Icon name="activity"/>{t("Real jobs. Visible progress.")}</span></div>
      </div><div className="auth-story-footer"><span className="status-dot"/>{t("Built for a clearer way to work.")}</div>
    </aside>
    <main className="auth-main"><div className="auth-top"><PreferenceControls/><Link href="/app">{t("Workspace")}<Icon name="chevron" size={15}/></Link></div>
      <div className="auth-card"><div className="auth-card-icon"><Icon name={register ? "spark" : "lock"} size={25}/></div><span className="overline">{t("Welcome to DataPilot")}</span><h2>{register ? t("Create your account.") : t("Sign in to your workspace.")}</h2><p>{register ? t("Create your account, then bring your first data sources together.") : t("Sign in to your workspaces, sources, and executions.")}</p>
        <div className="auth-tabs" role="group" aria-label={t("Account action")}><button type="button" className={!register ? "selected" : ""} onClick={() => {setRegister(false);setError("");}}>{t("Sign in")}</button><button type="button" className={register ? "selected" : ""} onClick={() => {setRegister(true);setError("");}}>{t("Create account")}</button></div>
        <form onSubmit={submit} aria-busy={busy}>{register && <label>{t("Your name")}<input autoComplete="name" name="name" placeholder="Zahra Oumous" required maxLength={120}/></label>}<label>{t("Email address")}<input type="email" name="email" autoComplete="email" placeholder="you@example.com" required maxLength={254}/></label><label>{t("Password")}<input type="password" name="password" autoComplete={register ? "new-password" : "current-password"} minLength={register ? 12 : 1} maxLength={128} required placeholder={register ? t("At least 12 characters") : t("Enter your password")}/></label>{register && <p className="field-help">{t("Use at least 12 characters. There are no default accounts.")}</p>}
          {error && <div className="notice error" role="alert"><Icon name="alert" size={18}/><span>{t(error)}</span></div>}
          <button className="btn primary auth-submit" disabled={busy} type="submit">{busy ? <><span className="spinner"/>{register ? t("Creating your account…") : t("Signing you in…")}</> : <>{register ? t("Create account") : t("Sign in")}<Icon name="arrow" size={17}/></>}</button>
        </form><div className="auth-security"><Icon name="shield" size={16}/><span>{t("Your workspaces are private to your account.")}</span></div>
      </div><footer className="auth-bottom">DataPilot AI <span>{t("Bring data together. Move forward with confidence.")}</span></footer>
    </main>
  </div>;
}
