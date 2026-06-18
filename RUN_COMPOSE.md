# RUN_COMPOSE.md — Hướng dẫn chạy Lab 05 (team-gate)

## Yêu cầu

- Docker Desktop ≥ 4.x (Compose v2)
- Git

## Clone và chạy

```bash
git clone https://github.com/Connectivity-services-ad-PT/lab-5-Onkilll123.git
cd lab-5-Onkilll123

# Copy file cấu hình
cp .env.example .env

# Build và chạy toàn bộ stack (3 container)
docker compose up -d --build
```

## Kiểm tra readiness

```bash
# API
curl http://localhost:8000/health

# AI Service
curl http://localhost:9000/health

# DB
docker exec fit4110-db-lab05 pg_isready -U lab05 -d gatedb
```

## Test API

```bash
# Tạo access event (card hợp lệ)
curl -X POST http://localhost:8000/access-events \
  -H "Authorization: Bearer local-dev-token" \
  -H "Content-Type: application/json" \
  -d '{"card_id":"CARD-2026-001","gate_id":"GATE-01","direction":"in","timestamp":"2026-06-18T08:00:00Z"}'

# Xem danh sách events
curl http://localhost:8000/access-events \
  -H "Authorization: Bearer local-dev-token"
```

## Dừng stack

```bash
docker compose down
# Hoặc xoá luôn volume DB
docker compose down -v
```

## Lệnh nhanh (Makefile)

```bash
make compose-up    # Build & run
make compose-down  # Stop & remove
make logs          # Xem log
make health        # Kiểm tra health
make test-compose  # Chạy Newman test
```

## Cấu trúc 3 service

| Service | Container | Port | Mô tả |
|---|---|---|---|
| api | fit4110-api-lab05 | 8000 | FastAPI Access Gate |
| db | fit4110-db-lab05 | 5432 (internal) | PostgreSQL |
| ai-service | fit4110-ai-lab05 | 9000 (internal) | AI Risk Mock |