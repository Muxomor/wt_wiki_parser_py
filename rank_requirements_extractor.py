import requests
import json
import csv
import re

DATA_URL = "https://cdn.jsdelivr.net/gh/gszabi99/War-Thunder-Datamine@master/char.vromfs.bin_u/config/rank.blkx"

type_mapping = {
    "Aircraft": "Авиация",
    "Helicopter": "Вертолёты",
    "Tank": "Наземная техника",
    "Ship": "Большой флот",
    "Boat": "Малый флот"
}

pattern = re.compile(r"needBuyToOpenNextInEra([A-Za-z]+)(\d+)")

def fetch_rank_data(url=DATA_URL):
    """Скачивает данные с указанного URL."""
    response = requests.get(url)
    response.raise_for_status()
    return response.text

def parse_rank_data(raw_data):
    """Парсит строку с данными как JSON."""
    return json.loads(raw_data)

def extract_rank_requirements(data):
    """
    Извлекает требования для открытия следующей эры.
    Для каждого ключа вида needBuyToOpenNextInEra<Type><n> интерпретируем:
      - предыдущий ранг = n
      - target_rank = n + 1
    Записи, где required_units равен 0, не включаются.
    """
    results = []
    era_data = data.get("needBuyToOpenNextInEra", {})
    for country_key, reqs in era_data.items():
        nation = country_key.replace("country_", "")
        for req_key, required_units in reqs.items():
            if required_units == 0:
                continue
            match = pattern.match(req_key)
            if match:
                raw_type, number_str = match.groups()
                try:
                    prev_rank = int(number_str)
                except ValueError:
                    continue
                target_rank = prev_rank + 1
                vehicle_type = type_mapping.get(raw_type)
                if not vehicle_type:
                    continue
                results.append({
                    "nation": nation,
                    "vehicle_type": vehicle_type,
                    "target_rank": target_rank,
                    "previous_rank": prev_rank,
                    "required_units": required_units
                })
    return results

def save_rank_requirements_to_csv(data, filename="rank_requirements.csv"):
    """Сохраняет извлечённые данные в CSV-файл."""
    fieldnames = ["nation", "vehicle_type", "target_rank", "previous_rank", "required_units"]
    with open(filename, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    print(f"Требования рангов сохранены в файл {filename}")

def run_rank_requirements_extraction():
    """
    Основная функция:
      1. Скачивает и парсит данные.
      2. Извлекает записи с требуемыми условиями (без required_units==0).
      3. Сохраняет результат в rank_requirements.csv.
    """
    raw_data = fetch_rank_data()
    parsed_data = parse_rank_data(raw_data)
    rank_requirements = extract_rank_requirements(parsed_data)
    save_rank_requirements_to_csv(rank_requirements)
