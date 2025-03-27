import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from page_helper import PageHelper  # Импортируем вспомогательный класс из отдельного модуля

def read_config(config_path='config.txt'):
    """
    Читает конфигурационный файл и возвращает словарь с параметрами.
    """
    config = {}
    try:
        with open(config_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' not in line:
                        print(f"Пропускаем некорректную строку #{line_num}: {line}")
                        continue
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()
    except Exception as e:
        raise RuntimeError(f"Ошибка чтения конфига: {str(e)}")
    return config

def configure_driver(config):
    """
    Настраивает и возвращает экземпляр Firefox драйвера на основе конфигурации.
    """
    options = Options()
    
    required = ['geckodriver_path', 'start_url']
    for param in required:
        if param not in config:
            raise ValueError(f"Отсутствует обязательный параметр: {param} в config.txt")
    
    # Если указан путь к firefox, задаем его в опциях
    if 'firefox_binary' in config and config['firefox_binary']:
        options.binary_location = config['firefox_binary']
    
    if config.get('headless', 'true').lower() == 'true':
        options.add_argument("--headless")
    
    # Отключаем загрузку изображений, если требуется
    if config.get('load_images', 'true').lower() == 'false':
        options.set_preference("permissions.default.image", 2)
    
    # Отключаем flash-плагин и кэширование
    options.set_preference("dom.ipc.plugins.enabled.libflashplayer.so", False)
    options.set_preference("browser.cache.disk.enable", False)
    options.set_preference("browser.cache.memory.enable", False)
    options.set_preference("network.http.use-cache", False)
    
    service = Service(
        executable_path=config['geckodriver_path'],
        log_path=os.devnull if config.get('disable_logs', 'false').lower() == 'true' else None
    )
    
    return webdriver.Firefox(service=service, options=options)

def main():
    try:
        print("Чтение конфигурационного файла...")
        config = read_config()
        print("Конфиг успешно загружен:")
        for key, value in config.items():
            print(f"   {key}: {value}")
        
        print("\nИнициализация Firefox драйвера...")
        driver = configure_driver(config)
        print("Драйвер успешно создан")
        
        helper = PageHelper(driver, wait_timeout=15)
        start_url = config['start_url']
        print(f"\nЗагрузка стартовой страницы: {start_url}")
        driver.get(start_url)
        print("Страница загружена")
        print(f"Заголовок страницы: {driver.title}")
        
        # Ожидаем появления контейнера с меню (например, с текстом VEHICLES)
        if not helper.wait_for_container():
            print("Не удалось обнаружить контейнер с меню, завершаем работу.")
            return
        
        # Определяем разделы, которые нужно обработать
        target_sections = [
            'Aviation', 'Helicopters', 'Ground Vehicles',
            'Bluewater Fleet', 'Coastal Fleet'
        ]
        
        for section in target_sections:
            try:
                # Ищем элемент навигационного меню для текущего раздела по XPath
                nav_item = helper.wait.until(
    EC.presence_of_element_located((By.XPATH, f"//a[contains(@class, 'layout-nav_item')]//span[normalize-space(text())='{section}']/.."))
)
                # Делаем клик по элементу, чтобы перейти в раздел
                print(f"\nНачинаем обработку раздела: {section}")
                nav_item.click()
                print(f"Переход в раздел {section} выполнен")
                
                # Ожидаем появления кнопки "List" по ID и кликаем по ней
                list_button = helper.wait_for_id('wt-show-list')
                if list_button:
                    try:
                        list_button.click()
                    except Exception as e:
                        print(f"Обычный клик не сработал: {str(e)}. Пробую JS click.")
                        driver.execute_script("arguments[0].click();", list_button)
                    print("Кнопка List активирована")
                    time.sleep(1)  # Пауза для обновления DOM
                    
                    # Обновляем список строк техники и получаем их общее количество
                    initial_rows = helper.get_vehicle_rows()
                    total_rows = len(initial_rows)
                    print(f"Общее количество строк техники: {total_rows}")
                    
                    # Итерируем по записям. На каждой итерации повторно получаем актуальные строки
                    for idx in range(total_rows):
                        try:
                            rows = helper.get_vehicle_rows()
                            if idx >= len(rows):
                                break
                            row = rows[idx]
                            
                            # Разбираем строку, используя позиционное обращение к ячейкам
                            cells = row.find_elements(By.TAG_NAME, 'td')
                            # Ссылка на подробности техники
                            try:
                                name_cell = row.find_element(By.CSS_SELECTOR, '.wt-ulist_unit-name a')
                                link = name_cell.get_attribute('href')
                            except Exception as e:
                                print(f"Ошибка при получении ссылки: {str(e)}")
                                link = ''
                            # Страна – из атрибута data-value ячейки с классом wt-ulist_unit-country
                            try:
                                country_cell = row.find_element(By.CSS_SELECTOR, 'td.wt-ulist_unit-country')
                                country = country_cell.get_attribute('data-value')
                            except Exception as e:
                                print(f"Ошибка при получении страны: {str(e)}")
                                country = ''
                            # Ранг – 4-я ячейка (если есть)
                            rank = cells[3].text.strip() if len(cells) > 3 else ''
                            # Battle rating – ячейка с классом "br" (обычно 5-я)
                            try:
                                battle_cell = row.find_element(By.CSS_SELECTOR, 'td.br')
                                battle_rating = battle_cell.text.strip()
                            except Exception as e:
                                print(f"Ошибка при получении battle_rating: {str(e)}")
                                battle_rating = ''
                            # Warpoints – 6-я ячейка (если есть); если текст равен "—", заменяем на пустую строку
                            warpoints = cells[5].text.strip() if len(cells) > 5 else ''
                            if warpoints == '—':
                                warpoints = ''
                            
                            data = {
                                'link': link,
                                'country': country,
                                'battle_rating': battle_rating,
                                'warpoints': warpoints,
                                'rank': rank
                            }
                            print(f"Запись {idx + 1}: {data}")
                        except Exception as e:
                            print(f"Ошибка при обработке записи {idx + 1}: {str(e)}")
                else:
                    print(f"Не удалось активировать List View для раздела {section}")
                
                # Задержка перед обработкой следующего раздела
                time.sleep(1)
            
            except Exception as e:
                print(f"Ошибка при обработке раздела {section}: {str(e)}")
                continue
        
        print("\nВсе разделы успешно обработаны!")
    
    except Exception as e:
        print(f"\nКритическая ошибка: {str(e)}")
    finally:
        if 'driver' in locals():
            driver.quit()
            print("Браузер закрыт")

if __name__ == "__main__":
    main()
