from typing import Optional, List
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

class PageHelper:
    def __init__(self, driver: WebDriver, wait_timeout: int = 10) -> None:
        """
        Инициализация помощника для работы со страницей
        
        :param driver: Экземпляр веб-драйвера
        :param wait_timeout: Время ожидания элементов (секунды)
        """
        self.driver = driver
        self.wait_timeout = wait_timeout
        self.wait = WebDriverWait(driver, wait_timeout)

    def wait_for_container(self) -> bool:
        """
        Ожидает появления контейнера с навигационными элементами.
        Контейнер определяется по наличию элемента с классом block и текстом VEHICLES.
        """
        try:
            self.wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[contains(@class, 'block') and .//div[contains(text(), 'VEHICLES')]]")
                )
            )
            return True
        except TimeoutException:
            print("Не удалось обнаружить контейнер с VEHICLES")
            return False

    def get_navigation_items(self) -> List[WebElement]:
        """
        Возвращает элементы навигационного меню.
        Ищет элементы вида: <a class="layout-nav_item">...</a>
        """
        try:
            return self.wait.until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, 'a.layout-nav_item')
                )
            )
        except TimeoutException:
            return []

    def click_list_button(self) -> bool:
        """
        Ожидает появления и кликает на кнопку переключения вида "List".
        Кнопка определяется по id="wt-show-list".
        """
        button = self.wait_for_id('wt-show-list')
        if button:
            button.click()
            return True
        return False

    def wait_for_id(self, element_id: str) -> Optional[WebElement]:
        """Ожидает появления элемента по ID."""
        try:
            return self.wait.until(EC.presence_of_element_located((By.ID, element_id)))
        except TimeoutException:
            return None

    def get_vehicle_rows(self) -> List[WebElement]:
        """
        Возвращает все строки с информацией о технике.
        Ищет элементы вида: <tr class="wt-ulist_unit wt-ulist_unit--regular" или wt-ulist_unit--prem ...>
        """
        # Можно объединить селекторы, если классы различаются
        return self.driver.find_elements(By.CSS_SELECTOR, 'tr.wt-ulist_unit')
    
    def parse_vehicle_row(self, row: WebElement) -> dict:
        """
        Извлекает данные из строки таблицы техники.
        
        :return: Словарь с ключами:
            - link: ссылка на подробности техники (из <a href="...">)
            - country: название страны (из data-value ячейки с классом wt-ulist_unit-country)
            - battle_rating: значение из ячейки с классом br
            - warpoints: число из ячейки стоимости (если отсутствует — пустая строка)
            - rank: текст из ячейки с данными ранга
        """
        data = {}
        try:
            # Ссылка на элемент – из первой ячейки, внутри <a href="...">
            name_cell = row.find_element(By.CSS_SELECTOR, '.wt-ulist_unit-name a')
            data['link'] = name_cell.get_attribute('href')
        except Exception as e:
            print(f"Ошибка при получении ссылки: {str(e)}")
            data['link'] = ''
    
        try:
            # Страна – извлекаем из атрибута data-value ячейки с классом wt-ulist_unit-country
            country_cell = row.find_element(By.CSS_SELECTOR, 'td.wt-ulist_unit-country')
            data['country'] = country_cell.get_attribute('data-value')
        except Exception as e:
            print(f"Ошибка при получении страны: {str(e)}")
            data['country'] = ''
    
        try:
            # Battle rating – значение из ячейки с классом br
            battle_cell = row.find_element(By.CSS_SELECTOR, 'td.br')
            data['battle_rating'] = battle_cell.text.strip()
        except Exception as e:
            print(f"Ошибка при получении battle_rating: {str(e)}")
            data['battle_rating'] = ''
    
        try:
            # Warpoints – пытаемся найти ячейку, содержащую число стоимости
            # Если значение равно "—" или отсутствует, возвращаем пустую строку
            warpoints_cell = row.find_element(By.XPATH, ".//td[@data-value and contains(., ',')]")
            text = warpoints_cell.text.strip()
            data['warpoints'] = text.split()[0] if text.split() and text.split()[0] != "—" else ''
        except Exception as e:
            print(f"Ошибка при получении warpoints: {str(e)}")
            data['warpoints'] = ''
    
        try:
            # Ранг – из ячейки с data-value, где содержится текст (например, <td data-value="2">II</td>)
            rank_cell = row.find_element(By.XPATH, ".//td[@data-value and not(contains(., ',')) and not(contains(@class, 'br'))]")
            data['rank'] = rank_cell.text.strip()
        except Exception as e:
            print(f"Ошибка при получении ранга: {str(e)}")
            data['rank'] = ''
    
        return data
