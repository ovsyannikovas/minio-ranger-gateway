# Проверка доступа по группам пользователей

## Как это работает

Gateway поддерживает проверку доступа как по пользователям, так и по группам пользователей, как это делается в Apache Ranger.

## Логика проверки

### В PolicyChecker (policy_parser.py)

```python
# Check users
policy_users = policy_item.get("users", [])
user_match = user in policy_users

# Check groups
policy_groups = policy_item.get("groups", [])
group_match = any(group in policy_groups for group in user_groups)

if not (user_match or group_match):
    continue  # Пользователь не совпадает ни по имени, ни по группе
```

**Логика:**
- Проверяется, есть ли пользователь в списке `users` политики **ИЛИ**
- Есть ли хотя бы одна группа пользователя в списке `groups` политики
- Если совпадает пользователь **ИЛИ** группа → проверяем дальше (ресурсы и тип доступа)
- Если не совпадает ни пользователь, ни группа → пропускаем эту политику

## Получение групп из Ranger UserSync

### Автоматическое получение

Gateway автоматически получает группы пользователя из Ranger UserSync через REST API:

```python
# В gateway.py
user_groups = await get_user_groups_from_ranger(user)
```

### Fallback через заголовок

Если группы не найдены в Ranger, можно использовать заголовок `X-User-Groups` как fallback:

```bash
curl -H "X-User: john" \
     -H "X-User-Groups: analysts,developers" \
     http://localhost:8000/analytics/
```

### Кэширование

Группы кэшируются в памяти (TTL 5 минут), чтобы не запрашивать их при каждом запросе.

Подробнее см. [USER_GROUPS.md](USER_GROUPS.md)

## Пример политики с группами

### JSON политики

```json
{
  "name": "analytics-group-policy",
  "service": "minio-service",
  "isEnabled": true,
  "resources": {
    "bucket": {
      "values": ["analytics"],
      "isExcludes": false
    }
  },
  "policyItems": [
    {
      "groups": ["analysts", "data-scientists"],
      "accesses": [
        {"type": "read", "isAllowed": true},
        {"type": "list", "isAllowed": true}
      ]
    },
    {
      "users": ["admin"],
      "groups": ["admins"],
      "accesses": [
        {"type": "read", "isAllowed": true},
        {"type": "write", "isAllowed": true},
        {"type": "delete", "isAllowed": true},
        {"type": "list", "isAllowed": true}
      ]
    }
  ]
}
```

### Примеры проверки

**Сценарий 1:** Пользователь `john` в группе `analysts`
- Запрос: `X-User: john`, `X-User-Groups: analysts`
- Политика: `groups: ["analysts", "data-scientists"]`
- ✅ **Результат:** Доступ разрешен (группа `analysts` совпадает)

**Сценарий 2:** Пользователь `jane` в группах `developers,testers`
- Запрос: `X-User: jane`, `X-User-Groups: developers,testers`
- Политика: `groups: ["analysts"]`
- ❌ **Результат:** Доступ запрещен (нет совпадения групп)

**Сценарий 3:** Пользователь `admin` напрямую
- Запрос: `X-User: admin`, `X-User-Groups: admins`
- Политика: `users: ["admin"]` ИЛИ `groups: ["admins"]`
- ✅ **Результат:** Доступ разрешен (совпадает пользователь)

## Важные моменты

1. **Логика OR**: Доступ разрешен, если пользователь совпадает **ИЛИ** хотя бы одна группа совпадает
2. **Пустые группы**: Если `groups` не указан в политике, проверяются только `users`
3. **Пустые users**: Если `users` не указан, проверяются только `groups`
4. **Оба указаны**: Если указаны и `users`, и `groups`, достаточно совпадения одного из них

## Будущие улучшения

Сейчас группы передаются через заголовок `X-User-Groups`. В будущем это можно улучшить:

1. **Из аутентификации**: Извлекать группы из JWT токена
2. **Из LDAP/AD**: Синхронизировать с корпоративным каталогом
3. **Из Ranger UserSync**: Использовать группы, синхронизированные Ranger'ом

