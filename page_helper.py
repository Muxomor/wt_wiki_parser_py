from typing import Optional, List
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import NoSuchElementException

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

    def wait_for_human_verification(self):
        """
        Если заголовок страницы равен 'Human Verification', ждем, пока пользователь не пройдет проверку.
        """
        while self.driver.title.strip().lower() == "human verification":
            input("Страница требует прохождения Human Verification. Пройдите проверку и нажмите Enter для продолжения...")

    def wait_for_container(self) -> bool:
        """
        Ожидает появления контейнера с навигационными элементами.
        Контейнер определяется по наличию элемента с классом block и текстом VEHICLES.
        """
        try:
            self.wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[contains(@class, 'block') and .//div[contains(text(), 'ТЕХНИКА')]]")
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
        Возвращает все строки с информацией о технике.\n
        Ищет элементы вида: tr class=wt-ulist_unit wt-ulist_unit--regular или wt-ulist_unit--prem...\n
        Для дальнейшего извлечения данных в методе parse_vehicle_row
        """
        return self.driver.find_elements(By.CSS_SELECTOR, 'tr.wt-ulist_unit')
    
    def get_country_buttons(self) -> dict:
        """
        Ищет кнопки стран в блоке unit-filter_country-buttons и собирает данные.
    
        :return: Словарь {ключ_страны: ссылка_на_изображение}
        """
        countries = {}
        try:
            buttons = self.wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.unit-filter_country-buttons button"))
            )
    
            for button in buttons:
                try:
                    # Извлекаем ключ из атрибута onclick
                    onclick_attr = button.get_attribute("onclick")
                    country_key = onclick_attr.split("'")[1] if onclick_attr else None
    
                    # Ищем тег <img> внутри кнопки и берем его src
                    img_tag = button.find_element(By.TAG_NAME, "img")
                    img_src = img_tag.get_attribute("src")
    
                    if country_key and img_src:
                        countries[country_key] = img_src
                except Exception as e:
                    print(f"Ошибка при обработке кнопки страны: {e}")
    
        except TimeoutException:
            print("Не найден блок unit-filter_country-buttons")
    
        return countries    

    def parse_vehicle_row(self, row: WebElement, category: str) -> dict:
        data = {}
        data['data_ulist_id'] = row.get_attribute("data-ulist-id") or ""
    
        try:
            name_link = row.find_element(By.CSS_SELECTOR, '.wt-ulist_unit-name a')
            data['link'] = name_link.get_attribute('href')
        except Exception as e:
            print(f"Ошибка при получении ссылки: {str(e)}")
            data['link'] = ''
    
        try:
            name_span = row.find_element(By.CSS_SELECTOR, '.wt-ulist_unit-name a span')
            data['name'] = name_span.text.strip()
        except Exception as e:
            print(f"Ошибка при получении названия: {str(e)}")
            data['name'] = ''
    
        try:
            country_cell = row.find_element(By.CSS_SELECTOR, 'td.wt-ulist_unit-country')
            data['country'] = country_cell.get_attribute('data-value')
        except Exception as e:
            print(f"Ошибка при получении страны: {str(e)}")
            data['country'] = ''
    
        try:
            battle_cell = row.find_element(By.CSS_SELECTOR, 'td.br')
            data['battle_rating'] = battle_cell.text.strip()
        except Exception as e:
            print(f"Ошибка при получении battle_rating: {str(e)}")
            data['battle_rating'] = ''
    
        try:
            silver_td = row.find_element(By.XPATH, ".//td[@data-value and contains(., ' ')]")
            silver = silver_td.text.replace(" ", "")
        except Exception as e:
            # Если не найден элемент или произошла ошибка, задаём пустую строку
            silver = ""
    
        # Если элемент содержит классы -prem или -squad, принудительно обнуляем silver
        row_class = row.get_attribute("class") or ""
        if "--prem" in row_class or "--squad" in row_class:
            silver = ""
    
        data["silver"] = silver
    
        try:
            cells = row.find_elements(By.TAG_NAME, 'td')
            data['rank'] = cells[3].text.strip() if len(cells) > 3 else ''
        except Exception as e:
            print(f"Ошибка при получении ранга: {str(e)}")
            data['rank'] = ''
    
        data['vehicle_category'] = category
        data['type'] = 'vehicle'
    
        return data