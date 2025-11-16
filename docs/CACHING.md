# Кэширование политик Ranger

## Проблема

Проверка политик через REST API Ranger на каждый запрос:
- Высокая латентность (сетевой запрос)
- Нагрузка на Ranger сервер
- Медленная работа gateway

## Решение: Кэширование

### Стратегия кэширования

1. **Кэш политик по ключу**: `(service, user, resource, accessType)`
2. **TTL**: 5-10 минут (настраивается)
3. **Инвалидация**: при изменении политик в Ranger

### Примеры из нативных плагинов

#### Hive Plugin

Hive plugin кэширует политики локально:
- Загружает политики при старте
- Обновляет по расписанию (каждые 5 минут)
- Использует in-memory кэш

#### Архитектура кэша

```
Policy Cache
├── Service Policies (по service name)
│   ├── Policy 1
│   ├── Policy 2
│   └── ...
└── Authorization Results (по запросу)
    ├── (user, resource, access) → isAllowed
    └── ...
```

### Реализация

#### Python cachetools

```python
from cachetools import TTLCache

policy_cache = TTLCache(maxsize=1000, ttl=300)  # 5 минут
```

#### Ключ кэша

```python
cache_key = (
    service_name,
    user,
    resource_bucket,
    resource_object,
    access_type
)
```

#### Проверка кэша

```python
def check_authorization(service, user, resource, access_type):
    cache_key = (service, user, resource['bucket'], resource.get('object'), access_type)
    
    if cache_key in policy_cache:
        return policy_cache[cache_key]
    
    # Запрос к Ranger
    result = ranger_client.authorize(service, user, resource, access_type)
    
    # Сохранение в кэш
    policy_cache[cache_key] = result
    return result
```

### Инвалидация кэша

1. **По TTL**: автоматически через cachetools
2. **Принудительно**: при изменении политик в Ranger
3. **По событию**: через webhook от Ranger (если поддерживается)

### Оптимизации

1. **Предзагрузка**: загрузить все политики при старте
2. **Batch проверки**: группировать проверки для одного пользователя
3. **Redis**: для распределенного кэша (опционально)

