import requests
from bs4 import BeautifulSoup
from typing import Dict
import time

class VehicleDataFetcher:
    @staticmethod
    def fetch_required_exp(vehicle_data: Dict[str, str]) -> Dict[str, str]:
        """
        Получает required_exp с указанной страницы и обновляет данные.
        
        :param vehicle_data: Исходный словарь с информацией о технике.
        :return: Обновленный словарь с добавленным required_exp (если найден).
        """
        if not vehicle_data.get("silver") or not vehicle_data.get("link"):
            return vehicle_data 
        
        try:
            time.sleep(0.10)  
            response = requests.get(vehicle_data["link"], headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")

            # Поиск всех блоков информации
            info_blocks = soup.find_all("div", class_="game-unit_card-info_item")
            for block in info_blocks:
                title_div = block.find("div", class_="game-unit_card-info_title")
                if title_div and "Исследование" in title_div.text:
                    value_div = block.find("div", class_="game-unit_card-info_value")
                    if value_div:
                        number_div = value_div.find("div")
                        if number_div and number_div.text:
                            required_exp = number_div.text.replace(" ", "").replace(".", "").strip()
                            vehicle_data["required_exp"] = required_exp
                            break

        except requests.RequestException as e:
            print(f"Ошибка запроса для {vehicle_data['link']}: {e}")
        except Exception as e:
            print(f"Ошибка парсинга для {vehicle_data['link']}: {e}")
        
        return vehicle_data
