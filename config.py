import os
from typing import List


def _parse_ids(value: str) -> List[int]:
    ids: List[int] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            # Игнорируем некорректные значения
            continue
    return ids


# Ожидаем переменную окружения ADMIN_USER_IDS вида: "123456789,987654321"
# Здесь это именно владельцы бота, которые могут выдавать права рассылки.
OWNER_USER_IDS = _parse_ids(os.getenv("ADMIN_USER_IDS", ""))
