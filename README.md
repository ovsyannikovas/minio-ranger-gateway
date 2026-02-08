# MinIO-Ranger Gateway

Шлюз для авторизации и аудита доступа к MinIO с помощью Apache Ranger.

**Установка**

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

init_ranger.py

Создает 2 тестовых юзера

user1 rangerR0cks!

user2 rangerR0cks!

Группу analytics, user2 в ней

Тестовые политики для проверки доступов:

        (f"{base_url}/policy", {
            "name": "minio-bucket-policy1",
            "description": "Access to entire bucket",
            "service": "minio-service",
            "isEnabled": True,
            "resources": {
                "bucket": {"values": ["analytics"], "isExcludes": False, "isRecursive": False}
            },
            "policyItems": [
                {
                    "groups": ["analytics"],
                    "accesses": [
                        {"type": "list", "isAllowed": True}
                    ]
                }
            ]
        }, "policy1"),
        (f"{base_url}/policy", {
            "name": "minio-bucket-policy2",
            "description": "Access to entire bucket",
            "service": "minio-service",
            "isEnabled": True,
            "resources": {
                "object": {"values": ["analytics/file.txt"], "isExcludes": False, "isRecursive": False}
            },
            "policyItems": [
                {
                    "users": ["user2"],
                    "accesses": [
                        {"type": "read", "isAllowed": True}
                    ]
                }
            ]
        }, "policy2")

Чтобы проверить работоспособность политик необходимо зайти в админку MinIO, создать бакет analytics и загрузить в него файл file.txt. 

Каждого пользователя нужно создать и выписать ключ к апи (Access key).

После этого можно попробовать получить доступ к файлу через MinIO CLI или через веб-интерфейс MinIO.

**Тестовые запросы для юзеров:**

В файле можно вставить ключи юзера и проверить основные запросы
```
python app/test/test_route.py
```