# Readiness Checklist — Lab 05 team-gate

Đánh dấu `[x]` khi mỗi mục đã pass trước khi tuyên bố stack sẵn sàng.

## 1. Database (PostgreSQL)
- [x] Container `fit4110-db-lab05` đang chạy (`docker ps`)
- [x] `pg_isready -U lab05 -d gatedb` trả về `accepting connections`
- [x] Bảng `access_events` và `cards` đã được tạo và seed

## 2. AI Service
- [x] Container `fit4110-ai-lab05` đang chạy
- [x] `GET http://localhost:9000/health` trả về `{"status":"ok"}`
- [x] `POST http://localhost:9000/predict` trả về `risk_level`

## 3. API — Kết nối DB và AI
- [x] `GET http://localhost:8000/health` trả về `{"status":"ok","db":"ok","ai":"ok"}`
- [x] `POST /access-events` tạo được event, lưu vào DB, trả về `ai_risk`
- [x] `GET /access-events` đọc được dữ liệu từ DB

## 4. Biến môi trường
- [x] `.env` được copy từ `.env.example`
- [x] Không có secret thật trong repo (không commit `.env`)
- [x] `AUTH_TOKEN` là `local-dev-token` cho môi trường dev

## 5. Network nội bộ
- [x] Network `team-internal` được tạo bởi Compose
- [x] API gọi được DB qua hostname `db`
- [x] API gọi được AI qua hostname `ai-service`

## 6. Version / Image Tag
- [x] Image tag theo quy ước: `v0.5.0-team-gate`
- [x] `SERVICE_VERSION=0.5.0` trong `.env`
- [x] `/health` trả về đúng version

---
*Checklist hoàn thành lúc: 2026-06-18*