import { useEffect, useState } from "react";
import { api } from "../api";

type User = { id: string; email: string; role: string };
export default function AccountSettings({token, admin, signedOut}: {token: string; admin: boolean; signedOut: () => void}) {
  const [users, setUsers] = useState<User[]>([]), [email, setEmail] = useState(""),
    [invitePassword, setInvitePassword] = useState(""), [currentPassword, setCurrentPassword] = useState(""),
    [password, setPassword] = useState(""), [message, setMessage] = useState(""), [busy, setBusy] = useState(false);
  useEffect(() => {
    if (admin) api<User[]>("/auth/users",token).then(setUsers).catch(e => setMessage(e.message));
  }, [admin, token]);
  return <section className="card">
    <h2>Your account</h2>
    <p className="muted">Passwords require at least 12 characters. Changing your password signs out all your sessions.</p>
    <form onSubmit={async e => {
      e.preventDefault(); setBusy(true); setMessage("");
      try { await api("/auth/password",token,{current_password:currentPassword,password}); signedOut(); }
      catch (e) {setMessage((e as Error).message);} finally {setBusy(false);}
    }}>
      <label>Current password<input type="password" autoComplete="current-password" minLength={12} maxLength={128} required value={currentPassword} onChange={e => setCurrentPassword(e.target.value)} /></label>
      <label>New password<input type="password" autoComplete="new-password" minLength={12} maxLength={128} required value={password} onChange={e => setPassword(e.target.value)} /></label>
      <button className="button secondary" disabled={busy}>Change password</button>
    </form>
    {admin && <>
      <h2>Account administration</h2>
      <p className="muted">Two administrators share the operator workspace. Each user has a private recovery workspace.</p>
      <ul>{users.map(u => <li key={u.id}>{u.email} · {u.role}</li>)}</ul>
      <form onSubmit={async e => {
        e.preventDefault(); setBusy(true); setMessage("");
        try {const user = await api<User>("/auth/users",token,{email,password:invitePassword});setUsers(old => [...old,user]);setEmail("");setInvitePassword("");setMessage("User created. Share the credentials privately.");}
        catch(e) {setMessage((e as Error).message);} finally {setBusy(false);}
      }}>
        <label>User email<input type="email" autoComplete="off" required value={email} onChange={e => setEmail(e.target.value)} /></label>
        <label>Initial password<input type="password" autoComplete="new-password" minLength={12} maxLength={128} required value={invitePassword} onChange={e => setInvitePassword(e.target.value)} /></label>
        <button className="button secondary" disabled={busy}>Create user</button>
      </form>
    </>}
    {message && <p role="status">{message}</p>}
  </section>;
}
