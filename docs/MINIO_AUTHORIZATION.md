# Авторизация в MinIO

## Обзор

MinIO использует S3-совместимый API и поддерживает несколько механизмов авторизации:

1. **IAM Policies** - JSON-политики, определяющие доступ к ресурсам
2. **Access Keys** - статические ключи доступа
3. **LDAP/Active Directory** - интеграция с корпоративными системами
4. **OpenID Connect** - OAuth2/OIDC интеграция

## S3 API Операции

### Основные операции

- **GET** - чтение объекта (`s3:GetObject`)
- **PUT** - запись объекта (`s3:PutObject`)
- **DELETE** - удаление объекта (`s3:DeleteObject`)
- **LIST** - список объектов в bucket (`s3:ListBucket`)

### Маппинг на Ranger Access Types

| S3 Operation | Ranger Access Type | HTTP Method |
|--------------|-------------------|-------------|
| GetObject | read | GET |
| PutObject | write | PUT/POST |
| DeleteObject | delete | DELETE |
| ListBucket | list | GET (bucket) |

## Структура запросов

### Bucket операции

```
GET /bucket-name/          → ListBucket
PUT /bucket-name/          → CreateBucket (не в scope)
DELETE /bucket-name/       → DeleteBucket (не в scope)
```

### Object операции

```
GET /bucket-name/object-key     → GetObject (read)
PUT /bucket-name/object-key     → PutObject (write)
DELETE /bucket-name/object-key → DeleteObject (delete)
```

## Извлечение информации из запроса

### Из URL

- **Bucket**: первый сегмент пути после `/`
- **Object**: остальная часть пути после bucket

Пример:
- URL: `/analytics/data/2024/file.csv`
- Bucket: `analytics`
- Object: `data/2024/file.csv`

### Из HTTP Headers

- **Authorization**: AWS Signature для аутентификации
- **x-amz-***: специфичные заголовки S3

## Важные замечания

1. MinIO не имеет нативной интеграции с Ranger
2. Необходимо использовать gateway для проверки политик
3. Gateway должен поддерживать AWS Signature для прозрачности для клиентов
4. Некоторые операции (CreateBucket, DeleteBucket) могут требовать специальной обработки

