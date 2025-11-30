# MinIO-Ranger Gateway Backend

## Архитектура

- **FastAPI Gateway**: API-прокси с авторизацией через Apache Ranger, proxy к MinIO.
- **MinIO**: Хранилище S3-совместимое.
- **Apache Ranger**: Централизованный сервис авторизации (RBAC/ABAC), REST-контроль политик.
- **Redis**: Кэш для пользователей, authorizations и групп.
- **Solr**: Аудит действий пользователей.
- **Kafka**: (опционально) очередь для сбора событий.

Схема: [проект-root]/docs/ARCHITECTURE.md

---

## Быстрый старт

```bash
# 1. Запустить все сервисы:
docker compose up --build

# 2. Инициализация (происходит автоматически при запуске gateway):
#   - Регистрация сервисов в Ranger
#   - Добавление дефолтных политик
#   - Запуск миграций

# 3. Проверка статуса gateway:
curl http://localhost:8000/api/v1/utils/health-check/
```

---

## Настройка окружения

В корне backend/ создайте .env (или скопируйте .env.example):
```
cp .env.example .env
```
Внесите значения:
- SECRET_KEY
- RANGER_* (HOST, USER, PASSWORD, SERVICE_NAME)
- MINIO_* (ENDPOINT, ROOT_USER, ROOT_PASSWORD)
- REDIS_*
- SOLR_AUDIT_URL

Генерация секрета:
```
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## Локальная разработка

```bash
# Установка зависимостей
uv sync

# Активация venv (если используется)
source .venv/bin/activate

# Линтинг, форматирование, mypy:
bash scripts/lint.sh
bash scripts/format.sh

# Запуск тестов:
bash scripts/test.sh
```

---

## Тесты и покрытие
Тесты лежат в backend/tests/ (интеграционные), см. также scripts/tests-start.sh для запуска контейнерного тестирования.

---

## Миграции и база данных

Миграции sqlmodel/alembic:
```bash
docker compose exec backend bash
alembic revision --autogenerate -m "add ..."
alembic upgrade head
```

---

### Endpoints
- Все API лежат под /api/v1
- Прокси-запросы S3: /{path:path}
- Healthcheck: /api/v1/utils/health-check/

---

## Для продакшна

- Обязательно ПРОПИШИТЕ уникальные значения SECRET_KEY, FIRST_SUPERUSER_PASSWORD, POSTGRES_PASSWORD, Ranger креды!
- Настройте monitoring за healthchecks.
- Проверьте миграции и инициализацию перед деплоем.


Документация по архитектуре — см. docs/ARCHITECTURE.md, CACHING.md, POLICY_PARSING.md и пр.
