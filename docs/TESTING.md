# Тестирование MinIO-Ranger Gateway

## Быстрый старт

### 1. Запустить все сервисы

```bash
docker-compose up -d
```

Это запустит:
- **Ranger**: zookeeper, solr, db, admin (порт 6080)
- **MinIO**: объектное хранилище (порты 9000, 9001)
- **Gateway**: FastAPI прокси (порт 8000)

### 2. Дождаться готовности сервисов

```bash
# Проверить статус
docker-compose ps

# Посмотреть логи
docker-compose logs -f gateway
docker-compose logs -f ranger-admin
```

Ranger может запускаться 2-3 минуты при первом запуске.

### 3. Создать сервис и политики в Ranger

```bash
make setup-minio-ranger
```

Это создаст:
- Service definition (`minio-service-def`)
- Service instance (`minio-service`)
- Пример политики

### 4. Проверить работу

```bash
# Проверить health check gateway
curl http://localhost:8000/api/v1/utils/health-check/

# Тест запроса к MinIO через gateway
curl -H "X-User: user1" http://localhost:8000/analytics/
```

## Структура сервисов

### Gateway (прокси)

**Не нужны:**
- ❌ Собственная БД (gateway не хранит данные)
- ❌ Prestart (нет миграций БД)
- ❌ Email сервисы

**Нужны:**
- ✅ FastAPI приложение
- ✅ Подключение к Ranger (для политик и групп)
- ✅ Подключение к MinIO (для проксирования)

### Порты

- **8000**: Gateway (FastAPI)
- **6080**: Ranger Admin UI
- **9000**: MinIO API
- **9001**: MinIO Console
- **8983**: Solr
- **2181**: ZooKeeper

## Тестирование

### 1. Проверка политик

```bash
# Создать политику для user1 на bucket analytics
# (через Ranger UI или API)

# Проверить доступ
curl -H "X-User: user1" http://localhost:8000/analytics/
# Должен вернуть список объектов или 403 если нет доступа
```

### 2. Проверка групп

```bash
# Если user1 в группе analysts в Ranger
curl -H "X-User: user1" http://localhost:8000/analytics/
# Gateway автоматически получит группы из Ranger
```

### 3. Проверка кэширования

```bash
# Первый запрос - загрузка политик и групп
curl -H "X-User: user1" http://localhost:8000/analytics/

# Второй запрос - из кэша (быстрее)
curl -H "X-User: user1" http://localhost:8000/analytics/
```

## Логи

```bash
# Логи gateway
docker-compose logs -f gateway

# Логи Ranger
docker-compose logs -f ranger-admin

# Логи MinIO
docker-compose logs -f minio
```

## Остановка

```bash
docker-compose down

# С удалением volumes
docker-compose down -v
```

## Переменные окружения

Gateway использует следующие переменные (установлены в docker-compose.yml):

```env
RANGER_HOST=http://ranger-admin:6080
RANGER_USER=admin
RANGER_PASSWORD=rangerR0cks!
RANGER_SERVICE_NAME=minio-service
RANGER_CACHE_TTL=300

MINIO_ENDPOINT=http://minio:9000
MINIO_ROOT_USER=admin
MINIO_ROOT_PASSWORD=password
```

## Troubleshooting

### Gateway не может подключиться к Ranger

Проверьте:
1. Ranger запущен: `docker-compose ps ranger-admin`
2. Health check прошел: `curl http://localhost:6080`
3. Сеть: gateway и ranger должны быть в одной сети `rangernw`

### Gateway не может подключиться к MinIO

Проверьте:
1. MinIO запущен: `docker-compose ps minio`
2. Health check: `curl http://localhost:9000/minio/health/live`
3. Сеть: gateway и minio должны быть в одной сети `rangernw`

### Политики не загружаются

Проверьте:
1. Сервис создан в Ranger: `make test-setup`
2. Логи gateway: `docker-compose logs gateway | grep policy`
3. Endpoint политик доступен: `curl -u admin:rangerR0cks! http://localhost:6080/plugins/policies?serviceName=minio-service`

