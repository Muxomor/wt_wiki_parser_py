import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support import expected_conditions as EC

from page_helper import PageHelper
from vehicle_get_required_exp import VehicleDataFetcher
from tree_data_extractor import TreeDataExtractor
from node_merger import NodesMerger
from data_utils import save_to_csv, save_dependencies_to_csv, get_all_nation_tree_data

def read_config(config_path='config.txt'):
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
        start_time = time.time()
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
        
        target_sections = [
            'Aviation', 
            #'Helicopters', 
            #'Ground Vehicles',
            #'Bluewater Fleet', 
            #'Coastal Fleet'
        ]
        
        # 1. Сбор данных из List View
        vehicles_data = []
        for section in target_sections:
            try:
                nav_item = helper.wait.until(
                    EC.presence_of_element_located(
                        (By.XPATH, f"//a[contains(@class, 'layout-nav_item')]//span[normalize-space(text())='{section}']/..")
                    )
                )
                print(f"\nНачинаем обработку раздела (List View): {section}")
                nav_item.click()
                print(f"Переход в раздел {section} выполнен")
                
                list_button = helper.wait_for_id('wt-show-list')
                if list_button:
                    try:
                        list_button.click()
                    except Exception as e:
                        print(f"Обычный клик не сработал: {e}. Пробую JS click.")
                        driver.execute_script("arguments[0].click();", list_button)
                    print("Кнопка List активирована")
                    #time.sleep(1)
                    
                    rows = helper.get_vehicle_rows()
                    total_rows = len(rows)
                    print(f"Общее количество строк техники: {total_rows}")
                    
                    for idx, row in enumerate(rows, start=1):
                        try:
                            data = helper.parse_vehicle_row(row, section)
                            data = VehicleDataFetcher.fetch_required_exp(data)
                            if data.get('silver'):
                                data['silver'] = int(data['silver'].replace(',', '').strip())
                            vehicles_data.append(data)
                            print(f"Запись {idx}: {data}")
                        except Exception as e:
                            print(f"Ошибка при обработке записи {idx}: {e}")
                else:
                    print(f"Не удалось активировать List View для раздела {section}")
                #time.sleep(1)
            except Exception as e:
                print(f"Ошибка при обработке раздела {section} (List View): {e}")
                continue
        
        print("\nСобранные данные из List View:")
        for idx, item in enumerate(vehicles_data, 1):
            print(f"Запись {idx}: {item}")
        
        save_to_csv(vehicles_data, filename="vehicles_list.csv")
        
        # 2. Сбор данных из Tree View
        tree_view_data = []
        for section in target_sections:
            try:
                print(f"\nПереходим в раздел (Tree View): {section}")
                nav_item = helper.wait.until(
                    EC.element_to_be_clickable(
                        (By.XPATH, f"//a[contains(@class, 'layout-nav_item')]//span[normalize-space(text())='{section}']/..")
                    )
                )
                nav_item.click()
                #time.sleep(2)
                
                # Сначала нажимаем кнопку Tree для текущего раздела
                tree_button = helper.wait.until(EC.presence_of_element_located((By.ID, "wt-show-tree")))
                driver.execute_script("arguments[0].click();", tree_button)
                print("Клик по кнопке Tree выполнен")
                #time.sleep(2)
                
                # Теперь перебираем вкладки наций для сбора данных
                section_tree_data = get_all_nation_tree_data(helper, section)
                print(f"Всего узлов из Tree View для раздела {section}: {len(section_tree_data)}")
                tree_view_data.extend(section_tree_data)
            except Exception as e:
                print(f"Ошибка при обработке раздела {section} (Tree View): {e}")
                continue
        
        save_to_csv(tree_view_data, filename="vehicles_tree.csv")
        
        # 3. Объединение данных и формирование зависимостей
        merger = NodesMerger(vehicles_data, tree_view_data)
        merged_data = merger.merge_data()
        dependencies = merger.extract_node_dependencies(merged_data)
        
        print("\nОбъединенные данные:")
        for idx, item in enumerate(merged_data, 1):
            print(f"Запись {idx}: {item}")
        
        print("\nИзвлеченные зависимости:")
        for dep in dependencies:
            print(dep)
        
        merged_fieldnames = [
            "data_ulist_id", "external_id", "link", "name", "country", "battle_rating",
            "silver", "rank", "vehicle_category", "type", "required_exp",
            "image_url", "parent_external_id", "column_index", "row_index", "order_in_folder"
        ]
        dep_fieldnames = ["node_external_id", "prerequisite_external_id"]
        
        save_to_csv(merged_data, filename="vehicles_merged.csv", fieldnames=merged_fieldnames)
        save_dependencies_to_csv(dependencies, filename="dependencies.csv", fieldnames=dep_fieldnames)
        
        end_time = time.time()
        elapse_time = end_time - start_time
        print(f"\nСкрипт выполнился за: {elapse_time:.2f} сек. ({elapse_time / 60:.2f} мин.)")
        
    except Exception as e:
        print(f"\nКритическая ошибка: {e}")
    finally:
        if 'driver' in locals():
            driver.quit()
            print("Браузер закрыт")

if __name__ == "__main__":
    main()
