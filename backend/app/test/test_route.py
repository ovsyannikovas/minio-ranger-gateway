# test_gateway_client.py
import os
import sys
import time
from datetime import datetime

import boto3
from botocore.client import Config

# Конфигурация
MINIO_ENDPOINT = "http://127.0.0.1:9000"  # Адрес вашего gateway
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID", "a5wxm8as2anLuyDGYLnu")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "TBowo7jHC9mmmVr6vAbLhmQrVWdI4fuU0c9ezvgo")
REGION = "us-east-1"

# Глобальные метрики
metrics = {
    'total_requests': 0,
    'successful_requests': 0,
    'failed_requests': 0,
    'total_time': 0.0,
    'requests_by_type': {},
    'errors': []
}


def print_metrics():
    """Вывод статистики выполнения"""
    print("\n" + "=" * 60)
    print("СТАТИСТИКА ВЫПОЛНЕНИЯ")
    print("=" * 60)
    print(f"Всего запросов: {metrics['total_requests']}")
    print(f"Успешных: {metrics['successful_requests']}")
    print(f"Неудачных: {metrics['failed_requests']}")
    print(f"Общее время: {metrics['total_time']:.3f} сек")
    print(f"Среднее время на запрос: {metrics['total_time'] / max(metrics['total_requests'], 1):.3f} сек")

    if metrics['requests_by_type']:
        print("\nПо типам запросов:")
        for req_type, count in metrics['requests_by_type'].items():
            print(f"  {req_type}: {count}")

    if metrics['errors']:
        print(f"\nОшибки ({len(metrics['errors'])}):")
        for i, error in enumerate(metrics['errors'][:5], 1):
            print(f"  {i}. {error}")
        if len(metrics['errors']) > 5:
            print(f"  ... и еще {len(metrics['errors']) - 5} ошибок")


def update_metrics(request_type: str, duration: float, success: bool, error: str = None):
    """Обновление метрик"""
    metrics['total_requests'] += 1
    metrics['total_time'] += duration

    if success:
        metrics['successful_requests'] += 1
    else:
        metrics['failed_requests'] += 1
        if error:
            metrics['errors'].append(f"{request_type}: {error}")

    if request_type in metrics['requests_by_type']:
        metrics['requests_by_type'][request_type] += 1
    else:
        metrics['requests_by_type'][request_type] = 1


def create_s3_client():
    """Создает S3 клиент для работы с MinIO gateway"""
    return boto3.client(
        's3',
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name=REGION,
        config=Config(signature_version='s3v4'),  # Важно для MinIO
        verify=False  # Отключаем проверку SSL для тестов
    )


def list_buckets():
    """Пример: список бакетов"""
    s3_client = create_s3_client()
    start_time = time.time()
    try:
        response = s3_client.list_buckets()
        duration = time.time() - start_time

        print("\n" + "=" * 50)
        print(f"СПИСОК БАКЕТОВ [{duration:.3f} сек]:")
        print("=" * 50)
        if response['Buckets']:
            for bucket in response['Buckets']:
                print(f"  - {bucket['Name']} (создан: {bucket['CreationDate']})")
        else:
            print("  Бакеты не найдены")

        update_metrics("list_buckets", duration, True)
        return response
    except Exception as e:
        duration = time.time() - start_time
        print(f"\nОШИБКА при получении списка бакетов [{duration:.3f} сек]: {e}")
        update_metrics("list_buckets", duration, False, str(e))
        return None


def put_object(bucket_name, object_key, data):
    """Пример: создать/обновить объект"""
    s3_client = create_s3_client()
    start_time = time.time()
    try:
        response = s3_client.put_object(
            Bucket=bucket_name,
            Key=object_key,
            Body=data
        )
        duration = time.time() - start_time

        print(f"\n✓ Объект '{object_key}' успешно загружен в бакет '{bucket_name}' [{duration:.3f} сек]")
        print(f"  ETag: {response.get('ETag', 'не указан')}")
        print(f"  Версия: {response.get('VersionId', 'не указана')}")

        update_metrics("put_object", duration, True)
        return response
    except Exception as e:
        duration = time.time() - start_time
        print(f"\n✗ ОШИБКА при загрузке объекта '{object_key}' [{duration:.3f} сек]: {e}")
        update_metrics("put_object", duration, False, str(e))
        return None


def get_object(bucket_name, object_key):
    """Пример: получить объект"""
    s3_client = create_s3_client()
    start_time = time.time()
    try:
        response = s3_client.get_object(
            Bucket=bucket_name,
            Key=object_key
        )
        data = response['Body'].read()
        duration = time.time() - start_time

        print(f"\n✓ Объект '{object_key}' успешно получен из бакета '{bucket_name}' [{duration:.3f} сек]")
        print(f"  Размер: {len(data)} байт")
        print(f"  Тип контента: {response.get('ContentType', 'не указан')}")
        print(f"  Содержимое: {data.decode('utf-8')[:100]}{'...' if len(data) > 100 else ''}")

        update_metrics("get_object", duration, True)
        return data
    except Exception as e:
        duration = time.time() - start_time
        print(f"\n✗ ОШИБКА при получении объекта '{object_key}' [{duration:.3f} сек]: {e}")
        update_metrics("get_object", duration, False, str(e))
        return None


def list_objects(bucket_name):
    """Пример: список объектов в бакете"""
    s3_client = create_s3_client()
    start_time = time.time()
    try:
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        duration = time.time() - start_time

        print(f"\n" + "=" * 50)
        print(f"ОБЪЕКТЫ В БАКЕТЕ '{bucket_name}' [{duration:.3f} сек]:")
        print("=" * 50)
        if 'Contents' in response:
            for obj in response['Contents']:
                print(f"  - {obj['Key']} (размер: {obj['Size']} байт, изменен: {obj['LastModified']})")
        else:
            print("  Объекты не найдены")

        update_metrics("list_objects", duration, True)
        return response
    except Exception as e:
        duration = time.time() - start_time
        print(f"\n✗ ОШИБКА при получении списка объектов [{duration:.3f} сек]: {e}")
        update_metrics("list_objects", duration, False, str(e))
        return None


def create_bucket(bucket_name):
    """Создать бакет"""
    s3_client = create_s3_client()
    start_time = time.time()
    try:
        response = s3_client.create_bucket(Bucket=bucket_name)
        duration = time.time() - start_time

        print(f"\n✓ Бакет '{bucket_name}' успешно создан [{duration:.3f} сек]")
        print(f"  Ответ: {response.get('ResponseMetadata', {}).get('HTTPStatusCode', 'неизвестно')}")

        update_metrics("create_bucket", duration, True)
        return response
    except Exception as e:
        duration = time.time() - start_time
        print(f"\n✗ ОШИБКА при создании бакета '{bucket_name}' [{duration:.3f} сек]: {e}")
        update_metrics("create_bucket", duration, False, str(e))
        return None


def run_performance_test():
    """Запуск тестов производительности"""
    print("\n" + "=" * 60)
    print("ТЕСТ ПРОИЗВОДИТЕЛЬНОСТИ")
    print("=" * 60)

    s3_client = create_s3_client()
    test_bucket = "performance-test"
    test_objects = 5

    # Очистка старого тестового бакета
    try:
        s3_client.delete_bucket(Bucket=test_bucket)
        print("Удален старый тестовый бакет")
    except:
        pass

    # Создание бакета
    start = time.time()
    s3_client.create_bucket(Bucket=test_bucket)
    create_time = time.time() - start

    # Загрузка нескольких объектов
    upload_times = []
    for i in range(test_objects):
        object_key = f"test-object-{i}.txt"
        data = b"X" * 1024  # 1KB данных

        start = time.time()
        s3_client.put_object(Bucket=test_bucket, Key=object_key, Body=data)
        upload_times.append(time.time() - start)

    # Чтение объектов
    read_times = []
    for i in range(test_objects):
        object_key = f"test-object-{i}.txt"

        start = time.time()
        s3_client.get_object(Bucket=test_bucket, Key=object_key)
        read_times.append(time.time() - start)

    # Список объектов
    start = time.time()
    s3_client.list_objects_v2(Bucket=test_bucket)
    list_time = time.time() - start

    # Удаление объектов
    delete_times = []
    for i in range(test_objects):
        object_key = f"test-object-{i}.txt"

        start = time.time()
        s3_client.delete_object(Bucket=test_bucket, Key=object_key)
        delete_times.append(time.time() - start)

    # Удаление бакета
    start = time.time()
    s3_client.delete_bucket(Bucket=test_bucket)
    delete_bucket_time = time.time() - start

    # Вывод результатов
    print(f"\nРезультаты теста производительности:")
    print(f"  Создание бакета: {create_time:.3f} сек")
    print(f"  Загрузка объектов (среднее): {sum(upload_times) / len(upload_times):.3f} сек")
    print(f"  Чтение объектов (среднее): {sum(read_times) / len(read_times):.3f} сек")
    print(f"  Список объектов: {list_time:.3f} сек")
    print(f"  Удаление объектов (среднее): {sum(delete_times) / len(delete_times):.3f} сек")
    print(f"  Удаление бакета: {delete_bucket_time:.3f} сек")
    print(f"  Всего операций: {test_objects * 3 + 3}")
    print(f"  Общее время: {time.time() - start:.3f} сек")


if __name__ == "__main__":
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ MINIO GATEWAY CLIENT")
    print("=" * 60)
    print(f"Начало теста: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Endpoint: {MINIO_ENDPOINT}")
    print(f"Access Key: {AWS_ACCESS_KEY[:10]}...")
    print(f"Region: {REGION}")
    print("=" * 60)

    start_time = time.time()

    try:
        # 1. Список бакетов
        print("\n1. Получение списка бакетов...")
        resp = list_buckets()

        # 2. Создание бакета (если нужно)
        test_bucket = "analytics"
        print(f"\n2. Создание бакета '{test_bucket}'...")
        resp = create_bucket(test_bucket)

        # 3. Загрузка объекта
        print(f"\n3. Загрузка тестового объекта в бакет '{test_bucket}'...")
        put_object(test_bucket, "test-object.txt", b"Hello from boto3 client!")

        # 4. Получение объекта
        print(f"\n4. Получение объекта 'test-object.txt' из бакета '{test_bucket}'...")
        data = get_object(test_bucket, "test-object.txt")

        # 5. Попытка получить несуществующий объект
        print(f"\n5. Попытка получить несуществующий объект 'file.txt'...")
        get_object(test_bucket, "file.txt")

        # 6. Список объектов в бакете
        print(f"\n6. Получение списка объектов в бакете '{test_bucket}'...")
        list_objects(test_bucket)

        # 7. Еще раз список бакетов
        print("\n7. Финальный список бакетов...")
        list_buckets()

        # 8. Дополнительный тест производительности (опционально)
        if len(sys.argv) > 1 and sys.argv[1] == "--perf":
            run_performance_test()

    except KeyboardInterrupt:
        print("\n\nТестирование прервано пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nКРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback

        traceback.print_exc()

    finally:
        total_duration = time.time() - start_time
        print(f"\nОбщее время выполнения: {total_duration:.3f} сек")
        print_metrics()

        print("\n" + "=" * 60)
        print(f"ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
        print(f"Завершено: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)