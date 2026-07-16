# DB CRM Frontend

Vue 3 + Vite + TypeScript frontend for the protected FastAPI backend.

## Local start

```bash
cd frontend-vue
cp .env.example .env.local
npm install
npm run dev
```

Open `http://localhost:5173`.

The browser talks to the backend through `VITE_API_BASE_URL`. For local Docker with backend published on port `8000`, keep:

```env
VITE_API_BASE_URL=http://localhost:8000
```

## Docker Compose service

Add this service next to `app` and `postgres` in `compose.yaml`:

```yaml
  frontend_vue:
    build:
      context: ./frontend-vue
    container_name: ${COMPOSE_PROJECT_NAME:-app}_frontend_vue
    environment:
      VITE_API_BASE_URL: "http://localhost:8000"
    ports:
      - "5173:5173"
    volumes:
      - ./frontend-vue:/app
      - /app/node_modules
    depends_on:
      - app
    restart: unless-stopped
```

The old Streamlit `frontend` service can be stopped or removed once Vue is the active UI.
