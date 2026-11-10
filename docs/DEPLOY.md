# Test deployment

This is a test site so other people can click through Rent It HQ. It is not the live business.

The website goes on Vercel. The API and Postgres go on Render. The browser should only see the Vercel address. Vercel forwards `/api`, `/admin`, and `/static` to Render. That keeps the login cookie on one site. If the page and the API were different sites, the browser would drop the cookie.

The Render address is not in the React code. The only place it goes is `frontend/vercel.json`, where it replaces the placeholder `RENDER_SERVICE_HOST`.

Do the Render service first. You need its hostname before the Vercel proxy can point at it.

## 1. Render

1. In the Render dashboard, choose New, then Blueprint. Point it at this repo. Render reads `render.yaml` from the root.
2. The blueprint creates a free web service named `rentithq-api` and a free Postgres database named `rentithq-db`, both in Frankfurt. If Render rejects that region, change both to the same region and apply again. They have to match.
3. Render asks for the values marked `sync: false`. Fill them before the first build. The list is in the next section. `DJANGO_SECRET_KEY` and `DATABASE_URL` are filled by the blueprint. Do not paste a database URL by hand.
4. Wait until the service is live. Open the service page and copy the hostname only, for example `rentithq-api.onrender.com`. No `https://`, no path. If the name was already taken, Render will have added a suffix. Use the hostname it actually shows.
5. Nothing else to run. On the free plan there is no shell or pre-deploy step, so every start runs `migrate` and then `seed_demo` before gunicorn. Both are safe to run again. If `DEMO_EMAIL` or `DEMO_PASSWORD` is missing, the seed is skipped and the app still starts.

The free web service sleeps after a quiet period. The first click after that can take about a minute. The free database is removed after 30 days unless you move it to a paid plan. Treat everything in it as disposable.

If migrations fail, the service will not start. The reason is in the Render logs.

Health: `https://THAT-HOST/api/v1/health/` should say `ok`. `https://THAT-HOST/api/v1/health/ready/` also checks Postgres.

## 2. Vercel

1. Import this repo. Set the root directory to `frontend`. Framework is Vite. Build command `npm run build`. Output directory `dist`. Leave the install command as `npm ci`.
2. Do not add an API address as an environment variable. The pages already call `/api/...`.
3. Open `frontend/vercel.json`. Replace every `RENDER_SERVICE_HOST` with the Render hostname from step 4 above. It appears four times and they must all match. Example shape, not a real service:

```json
"destination": "https://rentithq-api.onrender.com/api/:path*"
```

4. Deploy. The site URL will look like `https://something.vercel.app`.
5. Go back to Render and set the three address variables to that Vercel site. Save. Render will redeploy.
   - `DJANGO_ALLOWED_HOSTS`: the Vercel hostname, no scheme. Example `something.vercel.app`. Render's own hostname is added on its own.
   - `CSRF_TRUSTED_ORIGINS`: `https://something.vercel.app`
   - `FRONTEND_BASE_URL`: `https://something.vercel.app`

People should open the Vercel URL. Signing in on the `onrender.com` address stores a cookie the Vercel site cannot see. Django admin on the test site is `https://something.vercel.app/admin/`.

A Vercel preview URL is a different site. Add that hostname and its `https://` origin the same way if you want a preview to log in. I am not using a wildcard.

## Environment variables

### Render

| Name | What to put |
| --- | --- |
| `DJANGO_SETTINGS_MODULE` | `config.settings.production`. Already in the blueprint. |
| `DJANGO_DEBUG` | `false`. Already in the blueprint. |
| `DJANGO_SECRET_KEY` | Leave the generated value. If a build says it is too weak, replace it with a long random string of your own. Do not use a value that starts with `dev-`, `test-`, or `changeme`. |
| `DATABASE_URL` | Taken from `rentithq-db`. Do not type it. |
| `DB_CONN_MAX_AGE` | `0`. Already in the blueprint. |
| `PYTHON_VERSION` | `3.12.8`. Already in the blueprint. |
| `DJANGO_ALLOWED_HOSTS` | The Vercel hostname, no `https://`. Add another hostname with a comma if you attach a domain. Do not use `*`. |
| `CSRF_TRUSTED_ORIGINS` | `https://` plus the Vercel hostname. Separate extra origins with a comma. Each one must be https. |
| `FRONTEND_BASE_URL` | `https://` plus the Vercel hostname. Password-reset links use this. |
| `DEFAULT_FROM_EMAIL` | Already `Rent It HQ <noreply@rentithq.local>`. Change it when real mail is switched on. |
| `DEMO_EMAIL` | The sign-in address for the sample workspace. |
| `DEMO_PASSWORD` | A long password that is not a common word. The repo must never contain it. Running `seed_demo` again sets the account password to whatever is in this variable. |
| `PAYSTACK_SECRET_KEY` | A Paystack test secret, or leave it blank. A value that starts with `sk_live_` is refused. |
| `PAYSTACK_PUBLIC_KEY` | The matching test public key, or blank. |
| `EMAIL_HOST` | Leave blank. Mail is printed in the Render logs. |
| `EMAIL_PORT` | `587`. Already in the blueprint. Used only when `EMAIL_HOST` is set. |
| `EMAIL_HOST_USER` | Blank until you have SMTP. |
| `EMAIL_HOST_PASSWORD` | Blank until you have SMTP. Do not commit it. |
| `EMAIL_USE_TLS` | `true`. Already in the blueprint. |
| `RENDER_EXTERNAL_HOSTNAME` | Set by Render. Do not add it yourself. It is allowed as a host, and `https://` plus that host is trusted for CSRF, so the health check and a direct admin visit still work. |

`PAYSTACK_BASE_URL` can stay unset. It defaults to `https://api.paystack.co`.

When you do want real email, set `EMAIL_HOST` and the user and password, and set `DEFAULT_FROM_EMAIL` to an address that provider will send. Until then, nothing is mailed.

### Vercel

No environment variables for this test. The proxy host is the `RENDER_SERVICE_HOST` text in `frontend/vercel.json`.

## Demo workspace

`seed_demo` is safe to run again. It keeps one workspace named `DEMO workspace`, plan code `demo`, currency GHS, timezone Africa/Accra.

It adds, if they are missing:

- DEMO Harbour House, 14 Harbour Road, Osu, Accra, with Flat 1
- DEMO Ridge Court, 8 Ridge Road, Accra, with Room A
- Ama Mensah and Kojo Boateng as resident contacts

Those two contact addresses are sample data, not the login. The login is `DEMO_EMAIL`. The command does not print the password.

There is no Plan row, so the demo is not capped. Add a Plan in Django admin if you want to try the caps.

If that workspace is suspended, the command leaves it suspended and does not add rows.

## Paystack

Leave the keys blank until you want a test checkout. Use test keys only. The webhook Paystack should call is:

`https://YOUR-VERCEL-HOST/api/v1/billing/paystack/webhook/`

Paystack signs the raw body. A browser return from checkout is not a payment.

## What I still do by hand

- Create the Render blueprint and fill the blank environment values.
- Replace `RENDER_SERVICE_HOST` in `frontend/vercel.json`, then deploy Vercel with root directory `frontend`.
- Copy the Vercel hostname back into the three Render address variables.
- Nothing to run for the demo data. It seeds itself on start.
- `/admin/` needs a superuser. The free plan has no shell, so that waits for a paid plan or a one-off job.
- Paste Paystack test keys and the webhook, when I want to try a test charge.
- Point a custom domain, if I buy one. Then add that hostname the same way as the Vercel hostname.

SMS is not sent. There is no store app in this deploy.
