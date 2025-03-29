import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support import expected_conditions as EC
from page_helper import PageHelper
from vehicle_get_required_exp import VehicleDataFetcher

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
    
    if 'firefox_binary' in config and config['firefox_binary']:
        options.binary_location = config['firefox_binary']
    
    if config.get('headless', 'true').lower() == 'true':
        options.add_argument("--headless")
    
    if config.get('load_images', 'true').lower() == 'false':
        options.set_preference("permissions.default.image", 2)
    
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
        
        if not helper.wait_for_container():
            print("Не удалось обнаружить контейнер с меню, завершаем работу.")
            return
        
        # Определяем разделы для обработки
        target_sections = [
            'Aviation', 'Helicopters', 'Ground Vehicles',
            'Bluewater Fleet', 'Coastal Fleet'
        ]
        unqiue_countryes = set()
        
        for section in target_sections:
            try:
                # Ищем актуальный элемент раздела по XPath
                nav_item = helper.wait.until(
                    EC.presence_of_element_located(
                        (By.XPATH, f"//a[contains(@class, 'layout-nav_item')]//span[normalize-space(text())='{section}']/..")
                    )
                )
                print(unqiue_countryes)
                print(f"\nНачинаем обработку раздела: {section}")
                nav_item.click()
                print(f"Переход в раздел {section} выполнен")
                
                # Ожидаем кнопку "List" и кликаем по ней (используем JS-клик при необходимости)
                list_button = helper.wait_for_id('wt-show-list')
                if list_button:
                    try:
                        list_button.click()
                    except Exception as e:
                        print(f"Обычный клик не сработал: {str(e)}. Пробую JS click.")
                        driver.execute_script("arguments[0].click();", list_button)
                    print("Кнопка List активирована")
                    time.sleep(1)
                    
                    # Получаем актуальный список строк техники
                    initial_rows = helper.get_vehicle_rows()
                    total_rows = len(initial_rows)
                    print(f"Общее количество строк техники: {total_rows}")
                    
                    for idx in range(total_rows):
                        try:
                            rows = helper.get_vehicle_rows()
                            if idx >= len(rows):
                                break
                            row = rows[idx]
                            data = helper.parse_vehicle_row(row, section)
                            data = VehicleDataFetcher.fetch_required_exp(data)
                            print(f"Запись {idx + 1}: {data}")
                            #вытаскиваем все игровые нации
                            row_country = data['country']
                            if(row_country in unqiue_countryes):
                                continue
                            else:
                                unqiue_countryes.add(row_country)

                        except Exception as e:
                            print(f"Ошибка при обработке записи {idx + 1}: {str(e)}")
                else:
                    print(f"Не удалось активировать List View для раздела {section}")
                
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
