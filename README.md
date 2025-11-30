# MinIO-Ranger Gateway

**Шлюз для авторизации и аудита доступа к MinIO с помощью Apache Ranger.**

- Backend (FastAPI): описание и инструкции — см. [backend/README.md](backend/README.md)
- Инфраструктура, интеграции и архитектура — см. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Подробная документация (caching, группы, тестирование, политики) — в [docs/](docs/)

## TL;DR

```bash
docker compose up --build
```

Проект запустит:
- FastAPI gateway
- MinIO (S3 storage)
- Apache Ranger и Solr (аудит)
- Redis (кэш авторизации)
- Kafka (если нужен)

---

[Документация →](./docs/)
