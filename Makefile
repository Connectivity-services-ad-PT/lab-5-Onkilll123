.PHONY: compose-up compose-down logs test-compose build clean

compose-up: ## Build và chạy toàn bộ Compose stack
	cp -n .env.example .env 2>/dev/null || true
	docker compose up -d --build

compose-down: ## Stop và xoá stack
	docker compose down -v

logs: ## Xem log tất cả service
	docker compose logs -f

build: ## Build image
	docker compose build

test-compose: ## Chạy Newman test trên stack Compose
	npx newman run postman/FIT4110_lab05_gate.postman_collection.json \
		--environment postman/environments/FIT4110_lab05_local.postman_environment.json \
		--reporters cli,junit \
		--reporter-junit-export reports/newman-lab05-compose.xml

clean: ## Xoá image và volume
	docker compose down -v --rmi local

health: ## Kiểm tra health tất cả service
	@echo "=== API ==="
	@curl -sf http://localhost:8000/health | python -m json.tool || echo "API not ready"
	@echo "=== AI ==="
	@curl -sf http://localhost:9000/health | python -m json.tool || echo "AI not ready"
	@echo "=== DB ==="
	@docker exec fit4110-db-lab05 pg_isready -U lab05 -d gatedb || echo "DB not ready"