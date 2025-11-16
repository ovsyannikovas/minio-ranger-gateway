# Инструкция по созданию Custom Service в Apache Ranger для MinIO

## Обзор

Apache Ranger не имеет нативной поддержки MinIO, поэтому необходимо создать custom service definition и service instance.

## Шаги создания

### 1. Создание Service Definition

Service Definition определяет структуру ресурсов и операций для MinIO.

**REST API Endpoint:**
```
POST http://ranger-host:6080/public/v2/api/servicedef
```

**Тело запроса (servicedef.json):**
```json
{
  "name": "minio-service-def",
  "label": "MinIO",
  "description": "Custom service definition for controlling access to MinIO via Apache Ranger",
  "resources": [
    {
      "name": "bucket",
      "type": "string",
      "level": 1,
      "isExcludesSupported": true,
      "isRecursiveSupported": false,
      "matcher": "org.apache.ranger.plugin.resourcematcher.RangerDefaultResourceMatcher",
      "validationRegEx": "^[a-zA-Z0-9_.-]+$",
      "label": "Bucket"
    },
    {
      "name": "object",
      "type": "string",
      "level": 2,
      "isExcludesSupported": true,
      "isRecursiveSupported": true,
      "matcher": "org.apache.ranger.plugin.resourcematcher.RangerDefaultResourceMatcher",
      "validationRegEx": ".*",
      "label": "Object"
    }
  ],
  "accessTypes": [
    { "name": "read", "label": "Read" },
    { "name": "write", "label": "Write" },
    { "name": "delete", "label": "Delete" },
    { "name": "list", "label": "List" }
  ],
  "isEnabled": true
}
```

### 2. Создание Service Instance

Service Instance - это конкретный экземпляр сервиса с конфигурацией.

**REST API Endpoint:**
```
POST http://ranger-host:6080/public/v2/api/service
```

**Тело запроса (service.json):**
```json
{
  "name": "minio-service",
  "type": "minio-service-def",
  "configs": {
    "minioEndpoint": "http://minio:9000"
  },
  "description": "MinIO authorization policies"
}
```

### 3. Создание Policies

Политики определяют, кто и к чему имеет доступ.

**REST API Endpoint:**
```
POST http://ranger-host:6080/plugins/policies
```

**Тело запроса (policy.json):**
```json
{
  "name": "minio-bucket-policy",
  "description": "Access to entire bucket",
  "service": "minio-service",
  "isEnabled": true,
  "resources": {
    "bucket": {
      "values": ["analytics"],
      "isExcludes": false,
      "isRecursive": false
    }
  },
  "policyItems": [
    {
      "users": ["user1"],
      "accesses": [
        {"type": "read", "isAllowed": true},
        {"type": "write", "isAllowed": true},
        {"type": "list", "isAllowed": true}
      ]
    }
  ]
}
```

## Автоматизация через Makefile

Уже реализовано в `Makefile`:

```bash
make setup-minio-ranger  # Создает все: servicedef, service, policies
make create-service-def  # Только service definition
make create-service     # Только service instance
make create-policies    # Только policies
make clean-all          # Удаляет все созданное
```

## Проверка политик через REST API

Для проверки доступа используется endpoint:

```
POST http://ranger-host:6080/service/plugins/policies/authorize
```

**Тело запроса:**
```json
{
  "serviceName": "minio-service",
  "user": "user1",
  "userGroups": [],
  "accessType": "read",
  "resource": {
    "bucket": "analytics",
    "object": "data/file.csv"
  }
}
```

**Ответ:**
```json
{
  "isAllowed": true,
  "isAudited": true
}
```

## Важные замечания

1. **Аутентификация**: Все запросы к Ranger требуют Basic Auth (admin:password)
2. **Порядок создания**: Сначала servicedef, потом service, потом policies
3. **Имена ресурсов**: Должны соответствовать определению в servicedef
4. **Access types**: Должны соответствовать определению в servicedef

