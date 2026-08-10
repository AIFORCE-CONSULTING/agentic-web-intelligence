# Local Docker Environment

## Services

| Service | Address | Purpose |
|---|---|---|
| React operator console | http://localhost:3000 | User-facing platform shell |
| FastAPI platform API | http://localhost:8000/docs | API and future agent gateway |
| PostgreSQL | localhost:5432 | Durable platform data |
| Redis | localhost:6379 | Cache and coordination |

## Start the stack

1. Copy `.env.example` to `.env`.
2. Replace the development passwords in `.env`.
3. Start Docker Desktop and wait for its engine to report running.
4. Run `docker compose up --build`.

The first run downloads Linux base images and installs application dependencies inside the containers.

## Stop the stack

Run `docker compose down`. Add `--volumes` only when you intentionally want to remove local PostgreSQL and Redis data.
