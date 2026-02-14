FROM python:3.10-slim

WORKDIR /app

# Создаём директорию для данных
RUN mkdir -p /app/data

# Копируем зависимости и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код проекта
COPY . .

# Запускаем бота
CMD ["python", "bot.py"]