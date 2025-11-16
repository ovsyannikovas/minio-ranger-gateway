# Быстрый старт для тестирования

## Полный запуск проекта

### 1. Запустить все сервисы

```bash
docker-compose up -d
```

Это запустит:
- **Ranger**: zookeeper, solr, db, admin (порт 6080)
- **MinIO**: объектное хранилище (порты 9000, 9001)
- **Gateway**: FastAPI прокси (порт 8000)

### 2. Дождаться готовности

Ranger запускается 2-3 минуты при первом запуске. Проверить статус:

```bash
docker-compose ps
```

Проверить логи:

```bash
docker-compose logs -f gateway
docker-compose logs -f ranger-admin
```

### 3. Создать сервис в Ranger

```bash
make setup-minio-ranger
```

Это создаст:
- Service definition
- Service instance
- Пример политики

### 4. Проверить работу

```bash
# Health check
curl http://localhost:8000/api/v1/utils/health-check/

# Тест запроса (нужна политика в Ranger)
curl -H "X-User: user1" http://localhost:8000/analytics/
```

## Что НЕ нужно для Gateway

Gateway (прокси) **НЕ требует**:
- ❌ Собственную БД (PostgreSQL)
- ❌ Prestart (миграции БД)
- ❌ Email сервисы
- ❌ Пользовательские роуты (login, users, items)

Gateway **только**:
- ✅ Проксирует запросы к MinIO
- ✅ Проверяет политики через Ranger
- ✅ Получает группы пользователей из Ranger UserSync

## Порты

- **8000**: Gateway (FastAPI)
- **6080**: Ranger Admin UI
- **9000**: MinIO API
- **9001**: MinIO Console

## Структура docker-compose.yml

```
services:
  zookeeper      # Для Ranger
  ranger-solr    # Для Ranger (аудит)
  ranger-db      # PostgreSQL для Ranger
  ranger-admin   # Apache Ranger
  minio          # Объектное хранилище
  gateway        # FastAPI прокси (без БД!)
```

## Переменные окружения Gateway

В `docker-compose.yml` для gateway установлены:

```env
# Ranger
RANGER_HOST=http://ranger-admin:6080
RANGER_USER=admin
RANGER_PASSWORD=rangerR0cks!
RANGER_SERVICE_NAME=minio-service
RANGER_CACHE_TTL=300

# MinIO
MINIO_ENDPOINT=http://minio:9000
MINIO_ROOT_USER=admin
MINIO_ROOT_PASSWORD=password

# FastAPI (минимальные)
PROJECT_NAME=MinIO-Ranger Gateway
API_V1_STR=/api/v1
ENVIRONMENT=local
SECRET_KEY=changethis
```

**Важно**: БД не настроена для gateway, поэтому роуты, требующие БД, отключены автоматически.

## Остановка

```bash
docker-compose down

# С удалением volumes
docker-compose down -v
```

## Troubleshooting

### Gateway не запускается

Проверьте логи:
```bash
docker-compose logs gateway
```

### Gateway не может подключиться к Ranger

Проверьте:
1. Ranger запущен: `docker-compose ps ranger-admin`
2. Health check: `curl http://localhost:6080`
3. Сеть: все сервисы в сети `rangernw`

### Политики не загружаются

Проверьте:
1. Сервис создан: `make test-setup`
2. Логи: `docker-compose logs gateway | grep policy`

