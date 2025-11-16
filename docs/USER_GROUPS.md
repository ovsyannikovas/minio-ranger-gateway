# Получение групп пользователей из Ranger UserSync

## Обзор

Gateway автоматически получает группы пользователей из Ranger UserSync вместо передачи через заголовок. Это обеспечивает актуальность данных о группах и централизованное управление.

## Как это работает

### 1. Запрос групп из Ranger

При каждом запросе gateway:
1. Извлекает имя пользователя из запроса
2. Проверяет кэш групп пользователя
3. Если не в кэше → запрашивает из Ranger через REST API
4. Кэширует результат (TTL 5 минут)

### 2. API Endpoints

Пробуются следующие endpoints (по порядку):
- `/public/v2/api/user/{username}`
- `/public/v2/api/users/{username}`
- `/service/xusers/users/userName/{username}`
- `/service/xusers/users/name/{username}`
- `/service/users/{username}`

### 3. Парсинг ответа

Поддерживаются различные форматы ответа от Ranger:

```json
{
  "name": "john",
  "groups": ["analysts", "developers"]
}
```

или

```json
{
  "name": "john",
  "groupList": [
    {"name": "analysts"},
    {"name": "developers"}
  ]
}
```

или

```json
{
  "name": "john",
  "userGroups": ["analysts", "developers"]
}
```

### 4. Fallback

Если группы не найдены в Ranger:
- Возвращается пустой список
- Можно использовать заголовок `X-User-Groups` как fallback (если указан)

## Кэширование

Группы кэшируются в памяти:
- **TTL**: 5 минут
- **Max size**: 10000 пользователей
- Автоматическая инвалидация по TTL

## Использование

### В gateway.py

```python
# Get user groups from Ranger UserSync
user_groups = await get_user_groups_from_ranger(user)
if not user_groups:
    # Fallback to header if Ranger unavailable
    user_groups_str = request.headers.get("X-User-Groups", "")
    user_groups = [g.strip() for g in user_groups_str.split(",") if g.strip()]
```

### Пример запроса

```bash
# Группы будут получены автоматически из Ranger
curl -H "X-User: john" http://localhost:8000/analytics/

# Fallback через заголовок (если Ranger недоступен)
curl -H "X-User: john" \
     -H "X-User-Groups: analysts,developers" \
     http://localhost:8000/analytics/
```

## Настройка Ranger UserSync

Для работы необходимо настроить синхронизацию пользователей и групп в Ranger:

1. **LDAP/AD синхронизация**: Настроить подключение к LDAP/Active Directory
2. **File-based синхронизация**: Использовать CSV/JSON файлы
3. **Unix синхронизация**: Синхронизация из `/etc/passwd` и `/etc/group`

После настройки UserSync будет периодически синхронизировать пользователей и группы в Ranger.

## Логирование

- `INFO`: Успешная загрузка групп для пользователя
- `DEBUG`: Cache hit, попытки разных endpoints
- `WARNING`: Не удалось получить группы из всех endpoints

## Статистика кэша

Можно получить статистику кэша групп:

```python
from app.gateway.user_groups import get_user_groups_cache_stats

stats = get_user_groups_cache_stats()
# {
#   "size": 150,
#   "maxsize": 10000,
#   "ttl": 300
# }
```

## Очистка кэша

```python
from app.gateway.user_groups import clear_user_groups_cache

clear_user_groups_cache()
```

