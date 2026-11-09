# Deploying the Northstead Financial Advisor Copilot — step by step

No git or command line needed: everything happens in your web browser.
Total time: about 30–40 minutes. Do the steps **in this order**.

You'll end up with:
- **Render** (backend): `https://<your-name>.onrender.com`
- **Vercel** (the app you open on the laptop): `https://<your-name>.vercel.app`

---

## Step 1 — Two Claude API keys (5 min)

1. Go to **console.anthropic.com** and sign in.
2. Open **Settings → Workspaces** and create two workspaces:
   - `private-lane`
   - `public-lane`
3. In each workspace, open **API keys → Create key**. Name them `advisor-private` and `advisor-public`.
   Copy each key into a note right away — you won't be able to see it again.
4. Optional but recommended: in each workspace, set a **monthly spend limit** (for example $20).

Keeping the keys in separate workspaces means the Console shows usage per lane. You can show
that on stage next to the app's egress counter.

## Step 2 — Put the code on GitHub (5 min)

1. Unzip `finpilot-advisor.zip` on your computer. You'll get a folder `finpilot-advisor` that contains
   `backend`, `frontend`, `README.md` and `DEPLOY.md`.
2. On **github.com**, open the repository you created (for example `finpilot-advisor`).
3. Click **Add file → Upload files**.
4. Open the unzipped `finpilot-advisor` folder. Select **everything inside it** (backend, frontend,
   README.md, DEPLOY.md) and drag it onto the GitHub page.
   *Drag the contents, not the outer folder itself.* `backend` and `frontend` must sit at the top level of the repo.
5. Wait until every file has uploaded. Scroll down and click **Commit changes**.
6. Check: the repo's main page should list `backend`, `frontend`, `README.md` and `DEPLOY.md`.

> If GitHub complains about hidden files: the file `backend/.python-version` is optional and can be skipped.

## Step 3 — Backend on Render (10 min)

1. Go to **dashboard.render.com → New → Web Service**.
2. Connect your GitHub account if asked, then pick the `finpilot-advisor` repo.
3. Fill in:
   | Field | Value |
   |---|---|
   | Name | `northstead-advisor-backend` (any name is fine) |
   | Region | Oregon or Ohio — whichever is closest |
   | Branch | `main` |
   | **Root Directory** | `backend` |
   | Runtime / Language | Python 3 |
   | **Build Command** | `pip install -r requirements.txt` |
   | **Start Command** | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
   | Instance type | Free |
4. Open **Environment Variables** (on the same page, or under **Environment** after creating) and add:
   | Key | Value |
   |---|---|
   | `PRIVATE_LANE_API_KEY` | your **advisor-private** key |
   | `PUBLIC_LANE_API_KEY` | your **advisor-public** key |
   | `JWT_SECRET` | any long random text, e.g. `northstead-demo-7f3k29xq81` |
   | `GATEWAY_SIGNING_KEY` | a *different* long random text |
   | `APPROVAL_SIGNING_KEY` | another *different* long random text |
   | `FRONTEND_ORIGIN` | leave it for now — you'll add it in Step 5 |
   | `FINNHUB_API_KEY` | optional (live market news); skip it to use sample headlines |
5. Click **Create Web Service** and wait for the log to show `Application startup complete` (3–5 min).
6. Copy the service URL at the top of the page (for example `https://northstead-advisor-backend.onrender.com`).
   Open it in a new tab. You should see `{"status":"ok", ...}`.

## Step 4 — Frontend on Vercel (5 min)

1. Go to **vercel.com → Add New… → Project** and import the same `finpilot-advisor` repo.
2. Next to **Root Directory**, click **Edit** and choose `frontend`. The Framework Preset should switch to **Vite** automatically.
3. Open **Environment Variables** and add:
   | Key | Value |
   |---|---|
   | `VITE_BACKEND_URL` | your Render URL from Step 3, **with no slash at the end** |
4. Click **Deploy** and wait for it to finish (about 1 min).
5. Copy your Vercel URL (for example `https://finpilot-advisor.vercel.app`).
   Use the main **Domains** URL shown on the project page, not a long preview URL.

## Step 5 — Connect the two (3 min)

1. Back in **Render → your service → Environment**, add:
   | Key | Value |
   |---|---|
   | `FRONTEND_ORIGIN` | your Vercel URL, **with no slash at the end** |
2. Click **Save, rebuild, and deploy** (or **Save Changes**, then **Manual Deploy → Deploy latest commit**).
3. Wait for the deploy to finish.

Why both? The browser is only allowed to call the backend from the address listed in `FRONTEND_ORIGIN`.
The client-approval QR code also points at that address.

## Step 6 — Test it (5 min)

1. Open your Vercel URL. Sign in as **Jordan Lee** (password `demo123`).
2. Open **Aisha Rahman** and click the second suggestion.
   You should see tool calls stream in the trace, a reply, and a proposal card.
3. Click **Send to client for approval**. Scan the QR code with your phone and tap **Approve**.
   Aisha's card balance updates on screen within about 5 seconds.
4. In a new browser tab, sign in as **Taylor Brooks** (Compliance) and open **Governance console**. You'll see the decisions you just generated. (Advisors and tellers can't open it.)
5. Before the real demo, click **↺ Reset demo** (top right) to start clean.

---

## Troubleshooting

| What you see | Fix |
|---|---|
| Sign-in page says it can't reach the backend | Render's free tier sleeps after 15 minutes idle. Open the Render URL, wait 30–60 seconds, then refresh. |
| "No API key set for the private lane" in the copilot | Check `PRIVATE_LANE_API_KEY` / `PUBLIC_LANE_API_KEY` in Render, then redeploy. |
| Error mentioning the model name | Your key may not have access to the default model. In Render, set `PRIVATE_LANE_MODEL` and `PUBLIC_LANE_MODEL` to a model your Console lists (for example `claude-sonnet-4-5`), then redeploy. |
| Browser console shows a CORS error | `FRONTEND_ORIGIN` in Render must exactly match your Vercel URL: https, no trailing slash. |
| QR code opens a page that says "not found" | `FRONTEND_ORIGIN` is wrong or missing. Fix it and redeploy Render, then create a new proposal. |
| Everything worked, then proposals disappeared | The backend restarted (redeploy or sleep). Memory resets — that's expected. |

## Demo-day checklist

- [ ] 10 minutes before: open the Render URL so the backend wakes up, then open the app and click **↺ Reset demo**.
- [ ] Tab 1: **Jordan Lee** (advisor). Tab 2: **Morgan Wright** (supervisor), on the Approvals page. Tab 3: **Taylor Brooks** (compliance), on the Governance console. Only Supervisor and Compliance can open it.
- [ ] Phone ready to scan QR codes, on your own hotspot rather than venue Wi-Fi.
- [ ] Keep a backup screen recording.
- [ ] Say it once: "The private lane is Claude standing in for an on-prem model, and the gateway runs in-process for the demo."

## Pointing the private lane at a real on-prem model later

In Render, set:

```
PRIVATE_LANE_PROVIDER = openai
PRIVATE_LANE_BASE_URL = https://<your-model-server>/v1
PRIVATE_LANE_MODEL    = <model name on that server>
PRIVATE_LANE_API_KEY  = <its key, if it needs one>
```

This works with any OpenAI-compatible server (vLLM, Ollama, OpenShift AI, NIM). The label then changes from
"On-prem model (simulated)" to "On-prem model". Test tool calling carefully: small models are less reliable at it than Claude.
