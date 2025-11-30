FROM python:3.10

# Установка системных зависимостей
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        python3-dev \
        curl && \
    rm -rf /var/lib/apt/lists/*

# Установка Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Добавляем Poetry в PATH
ENV PATH="${PATH}:/root/.local/bin"

# Настройка Poetry
ENV POETRY_VIRTUALENVS_IN_PROJECT=true
ENV POETRY_NO_INTERACTION=1

WORKDIR /app

# Копируем нужные файлы для установки зависимостей
COPY pyproject.toml README.md poetry.lock* ./

# Устанавливаем зависимости (это создаст .venv в /app)
RUN poetry install --no-root

# Копируем код
COPY scripts /app/scripts
COPY app /app/app

# Устанавливаем PYTHONPATH
ENV PYTHONPATH=/app

# Активируем виртуальное окружение в PATH
ENV PATH="/app/.venv/bin:${PATH}"

# Устанавливаем проект в режиме разработки
RUN poetry install

# Запуск приложения напрямую из виртуального окружения
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]