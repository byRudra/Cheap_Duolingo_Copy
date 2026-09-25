# Duolingo frontend

This is the Next.js (App Router) frontend for the Duolingo demo app. Full setup, architecture and demo instructions are in the [root README](../README.md).

```bash
npm install
cp .env.example .env.local   # PowerShell: Copy-Item .env.example .env.local
npm run dev                  # http://localhost:3000 (backend expected on :8000)
npm run build                # production build; `npm start` serves it
```

`NEXT_PUBLIC_API_URL` is inlined at build time, so rebuild after changing it.
