# AK Builders — Free (₹0) Deployment Guide

| Part | Service (free plan) | Address you get |
|---|---|---|
| Code | GitHub (private repo) | github.com/<you>/ak-builders |
| Database | Neon Postgres | connection link |
| Photos / bills / logo | Cloudinary | res.cloudinary.com/... |
| Backend API | Render (Docker, free) | https://akbuilders-api.onrender.com |
| Frontend | Cloudflare Pages | https://akbuilders.pages.dev |
| Daily job + DB backup | GitHub Actions | runs 02:00 IST |

No credit card is needed for any of these. Do the steps in order.

---

## 1. Put the code on GitHub (private)
1. Install **GitHub Desktop** (desktop.github.com) and sign in with your GitHub account.
2. **File → Add local repository** → choose `D:\Sajo Projects\AK Builders`.
   It says "not a Git repository" → click **create a repository** → **Create repository**.
3. In the left list of changed files, check that **no `.env` file, `venv`, `node_modules` or `_to_delete`**
   appears (`.gitignore` already excludes them).
4. Summary: `AK Builders - free deployment` → **Commit to main**.
5. **Publish repository** → name `ak-builders` → keep **"Keep this code private" ticked** → **Publish**.

## 2. Database — Neon
1. Sign up at neon.tech → **Create project**: name `akbuilders`, Postgres latest, region **AWS Asia Pacific (Singapore)**.
2. **Connect** → copy the connection string (pooled). It looks like
   `postgresql://user:pass@ep-xxxx-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require`
   This is your **DATABASE_URL**. Keep it secret.

## 3. Files — Cloudinary
1. Sign up at cloudinary.com (free).
2. Dashboard → **API Keys** → copy the **API environment variable**
   `cloudinary://<api_key>:<api_secret>@<cloud_name>` → this is your **CLOUDINARY_URL**.
3. **Settings → Security** → turn ON **"Allow delivery of PDF and ZIP files"**
   (needed for PDF expense bills to open).

## 4. Backend — Render
1. Sign up at render.com with your GitHub account.
2. **New → Blueprint** → choose the `ak-builders` repo. Render reads `render.yaml`.
3. Fill the values it asks for:
   - `DATABASE_URL` → from step 2
   - `CLOUDINARY_URL` → from step 3
   - `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `FRONTEND_URL` → put `https://akbuilders.pages.dev`
     for now (fix it in step 6 if Cloudflare gives a different name)
   - `ADMIN_URL` → a hidden path, e.g. `office-7f3k2/`
4. **Apply**. The first build takes ~5–8 min. Migrations run automatically.
5. Open `https://<your-service>.onrender.com/api/v1/health/` → should show `"status": "ok"`.

## 5. Create roles + your admin login (one time, from your PC)
> **Just a demo?** Skip this step. `render.yaml` has `SEED_ON_START=True`, so Render creates the
> roles, sample materials and the `admin` login (with the `DEMO_ADMIN_PASSWORD` you typed in step 4)
> automatically. You will be asked to change the password at first login.
> **Demo tip:** open the site 1–2 minutes before showing it, so the free server is already awake.

Render's free plan has no shell, so run this once on your PC against the Neon database.
In PowerShell:
```
cd "D:\Sajo Projects\AK Builders\backend"
venv\Scripts\python.exe -m pip install -r requirements.txt
$env:DATABASE_URL = "<your Neon connection string>"
$env:DEMO_ADMIN_USERNAME = "sathish"
$env:DEMO_ADMIN_EMAIL = "<your email>"
$env:DEMO_ADMIN_PASSWORD = "<a strong password>"
venv\Scripts\python.exe manage.py seed_data
Remove-Item Env:DATABASE_URL, Env:DEMO_ADMIN_PASSWORD
```
This creates the 5 roles, company settings, sample materials and your Super Admin user.
(Never use the demo password `Admin@12345` on the live site.)

**Moving existing data from your PC instead?** Dump the local DB and load it into Neon:
```
pg_dump --no-owner --no-acl -d arbuilders -U postgres -f akb.sql
psql "<your Neon connection string>" -f akb.sql
```
(Do this *before* step 4, or on an empty Neon database.) Old uploaded photos stay on your PC —
re-upload the company logo in Settings after going live.

## 6. Frontend — Cloudflare Pages
1. Sign up at dash.cloudflare.com → **Workers & Pages → Create → Pages → Connect to Git** → pick the repo.
2. Build settings:
   - Framework preset: **Vite** (or None)
   - Root directory: `frontend`
   - Build command: `npm run build`
   - Build output directory: `dist`
   - Environment variables: `VITE_API_URL` = `https://<your-service>.onrender.com`  (no `/` at the end)
     and `NODE_VERSION` = `20`
3. **Save and Deploy**. You get `https://<name>.pages.dev`.
4. If the name is not `akbuilders.pages.dev`, go back to Render → your service → **Environment** and
   update `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` and `FRONTEND_URL` to the real address. Render redeploys.

## 7. Daily job + backups — GitHub Actions
1. GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**
   - Name `DATABASE_URL`, value = Neon connection string.
2. **Actions** tab → "Daily jobs" → **Run workflow** once to test.
   Every night it expires old quotations and saves a database backup (download it from the
   run's **Artifacts**, kept 14 days). Download one every week or two and keep it safe.

## 8. Log in
Open `https://<name>.pages.dev` → log in with the user from step 5 → Settings → company profile & logo.

---

## Things to know about the free plan
- **Sleep:** the backend sleeps after 15 min with no use. The first request after that takes
  up to ~1 minute; after that it is fast. Upgrading Render (paid) removes this.
- **Limits:** Neon 1 GB data (years of text records for one company), Cloudinary 25 credits/month
  (≈ 25 GB storage + bandwidth combined), Render 750 hours/month (enough for 1 service).
- **Password-reset emails** are not sent until email is set up. Free option: a Gmail account with an
  App Password — add on Render: `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`,
  `EMAIL_HOST=smtp.gmail.com`, `EMAIL_HOST_USER=<gmail>`, `EMAIL_HOST_PASSWORD=<app password>`,
  `DEFAULT_FROM_EMAIL=AK Builders <gmail>`. Until then, an Admin can reset passwords in Users.
- **Updates:** `git push` → Render and Cloudflare redeploy automatically.
- **Custom domain** (optional, the only paid item ~₹500–900/year): add it in Cloudflare Pages, and
  e.g. `api.akbuilders.in` in Render; then add both to the Render environment values.
