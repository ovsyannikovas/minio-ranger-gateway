# Парсинг и проверка политик Ranger

## Обзор

Вместо использования несуществующего API endpoint `/policy/authorize`, gateway загружает все политики из Ranger и проверяет их локально, как это делают нативные плагины Ranger (Hive, HDFS и т.д.).

## Загрузка политик

### Endpoint

Политики загружаются через GET запрос:
```
GET /plugins/policies?serviceName=minio-service
```

Или альтернативные endpoints:
```
GET /public/v2/api/service/name/minio-service/policies
GET /public/v2/api/policy?serviceName=minio-service
```

### Формат политики

```json
{
  "id": 1,
  "name": "minio-bucket-policy",
  "service": "minio-service",
  "isEnabled": true,
  "isAuditEnabled": true,
  "resources": {
    "bucket": {
      "values": ["analytics"],
      "isExcludes": false,
      "isRecursive": false
    },
    "object": {
      "values": ["data/*"],
      "isExcludes": false,
      "isRecursive": true
    }
  },
  "policyItems": [
    {
      "users": ["user1"],
      "groups": ["analysts"],
      "accesses": [
        {"type": "read", "isAllowed": true},
        {"type": "write", "isAllowed": true},
        {"type": "list", "isAllowed": true}
      ]
    }
  ]
}
```

## Логика проверки

### 1. Матчинг ресурсов

#### Bucket
- Точное совпадение имени bucket
- Поддержка `isExcludes` (исключения)

#### Object
- Точное совпадение или префикс (если `isRecursive: true`)
- Поддержка `isExcludes` (исключения)

### 2. Матчинг пользователя/группы

Проверяется:
- Пользователь в списке `users` политики
- ИЛИ группа пользователя в списке `groups` политики

### 3. Матчинг типа доступа

Проверяется, что запрашиваемый `access_type` (read/write/delete/list) есть в списке разрешенных `accesses` с `isAllowed: true`.

## Алгоритм проверки

```
Для каждой политики:
  1. Если политика disabled → пропустить
  2. Проверить матчинг bucket
  3. Если object_path есть → проверить матчинг object
  4. Проверить матчинг user или group
  5. Проверить матчинг access_type
  6. Если все совпало → разрешить доступ
  7. Если ни одна политика не совпала → запретить доступ
```

## Примеры

### Пример 1: Доступ к bucket

**Политика:**
```json
{
  "resources": {
    "bucket": {"values": ["analytics"]}
  },
  "policyItems": [{
    "users": ["user1"],
    "accesses": [{"type": "list", "isAllowed": true}]
  }]
}
```

**Запрос:** `user1` → `GET /analytics/`
- ✅ Bucket совпадает
- ✅ User совпадает
- ✅ Access type "list" разрешен
- **Результат:** Разрешено

### Пример 2: Доступ к object

**Политика:**
```json
{
  "resources": {
    "bucket": {"values": ["analytics"]},
    "object": {"values": ["data/*"], "isRecursive": true}
  },
  "policyItems": [{
    "users": ["user1"],
    "accesses": [{"type": "read", "isAllowed": true}]
  }]
}
```

**Запрос:** `user1` → `GET /analytics/data/file.csv`
- ✅ Bucket совпадает
- ✅ Object path "data/file.csv" начинается с "data/*"
- ✅ User совпадает
- ✅ Access type "read" разрешен
- **Результат:** Разрешено

### Пример 3: Исключение

**Политика:**
```json
{
  "resources": {
    "bucket": {"values": ["analytics"]},
    "object": {"values": ["private/*"], "isExcludes": true, "isRecursive": true}
  },
  "policyItems": [{
    "users": ["user1"],
    "accesses": [{"type": "read", "isAllowed": true}]
  }]
}
```

**Запрос:** `user1` → `GET /analytics/private/secret.txt`
- ✅ Bucket совпадает
- ❌ Object path "private/secret.txt" в исключениях
- **Результат:** Запрещено (исключение)

## Периодическое обновление

Политики обновляются:
- При старте приложения
- Каждые 5 минут (настраивается через `RANGER_CACHE_TTL`)
- В фоновом режиме (не блокирует запросы)

## Кэширование

1. **Кэш политик**: Хранит все политики сервиса в памяти
2. **Кэш результатов**: Кэширует результаты проверки (TTL 5 минут)

Это позволяет:
- Быструю проверку без обращения к Ranger
- Работу при временной недоступности Ranger
- Снижение нагрузки на Ranger сервер

