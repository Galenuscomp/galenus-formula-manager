// Same rules as backend app/security.py password_problems; the server has the final say.
export const PASSWORD_MIN_LENGTH = 10;

export function passwordRules(password, email = "") {
  const local = (email.split("@")[0] || "").toLowerCase();
  return [
    { label: `At least ${PASSWORD_MIN_LENGTH} characters`, ok: password.length >= PASSWORD_MIN_LENGTH },
    { label: "At least one letter", ok: /\p{L}/u.test(password) },
    { label: "At least one digit", ok: /\p{Nd}/u.test(password) },
    {
      label: "Does not contain your e-mail address",
      ok: password.length > 0 && !(local.length >= 3 && password.toLowerCase().includes(local)),
    },
  ];
}

export const passwordOk = (password, email) => passwordRules(password, email).every((r) => r.ok);
