Frontend (Vite + React)
=========================

Run the dev frontend and proxy API requests to the backend.

Setup
```
cd frontend
npm install
```

Install backend dependencies
```
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Start backend (in separate terminal)
```
cd backend
source .venv/bin/activate
python main.py
```

Skip external API sync while debugging routes
```
cd backend
source .venv/bin/activate
RUN_STARTUP_SYNC=0 python main.py
```

Start frontend
```
cd frontend
npm run dev
```

Open: http://localhost:5173

Notes
- The Vite dev server proxies `/query` and `/health` to `http://localhost:8000` so CORS won't block requests in development.
- If you still see errors, open browser DevTools -> Network and inspect the failing request body and response.
# React + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.
