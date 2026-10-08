# Campus Customs Desk (frontend)

React + Vite + TypeScript dashboard for the Campus Customs agent team.

```bash
npm install      # once
npm run dev      # opens http://localhost:5173
```

The backend must be running at `http://localhost:8000` (set in `.env` as `VITE_API_BASE`):

```bash
cd ../backend
uvicorn main:app --reload --port 8000
```

- `src/App.tsx`: polling, launching runs, approvals, reset
- `src/api.ts`: one function per backend route
- `src/teamState.ts`: turns the event feed into "who is saying/doing what"
- `src/components/`: city background, ticket lanes, playfield bumpers, agent comm cards, cash LED, approval console, debrief, transmission log

Design notes: `../output/design.md`.
