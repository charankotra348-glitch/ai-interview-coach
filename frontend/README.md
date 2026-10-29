# Frontend

Next.js 16 app for AI Interview Coach. See the [main README](../README.md) for what the project does and how to run everything.

```bash
cp .env.example .env.local   # BACKEND_URL, default http://127.0.0.1:8000
npm ci
npm run dev                  # http://localhost:3000
```

| Command | What it runs |
|---|---|
| `npm test` | Vitest unit tests |
| `npm run lint` | ESLint |
| `npm run typecheck` | Generated route types + `tsc --noEmit` |
| `npm run build` | Production build |

**How it talks to the API:** the browser only ever calls this Next.js server. `app/api/auth/*` signs users in and keeps the access token in an httpOnly cookie; `app/api/backend/[...path]` forwards every other call to FastAPI with the token attached. `proxy.ts` sends signed-out visitors to `/login`. Why: [decision 006](../docs/decisions/006-backend-for-frontend-httponly-cookie.md).

| Page | What's on it |
|---|---|
| `/register`, `/login` | Account |
| `/dashboard` | Resume and job upload, skill gap, start an interview, past interviews |
| `/interview/[id]` | One question at a time, answer box, rubric feedback after each answer |
| `/interview/[id]/summary` | Scores per criterion, follow-up effect, difficulty path, cost |
