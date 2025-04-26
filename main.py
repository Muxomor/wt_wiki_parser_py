import os
import time
# import logging # Убрано
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException 
from db_uploader import upload_all_data
from page_helper import PageHelper
from vehicle_get_required_exp import VehicleDataFetcher
from node_merger import NodesMerger
from data_utils import save_to_csv, save_dependencies_to_csv, get_all_nation_tree_data, save_country_flags_to_csv

def read_config(config_path='config.txt'):
    """Читает конфигурационный файл."""
    config = {}
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' not in line:
                        print(f"Предупреждение: Пропускаем некорректную строку #{line_num} в config.txt: {line}")
                        continue
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()
    except FileNotFoundError:
         raise RuntimeError(f"КРИТИЧЕСКАЯ ОШИБКА: Конфигурационный файл '{config_path}' не найден.")
    except Exception as e:
        raise RuntimeError(f"КРИТИЧЕСКАЯ ОШИБКА: Ошибка чтения конфига '{config_path}': {str(e)}")
    return config

def configure_driver(config):
    """Настраивает и возвращает экземпляр WebDriver."""
    options = Options()
    required = ['geckodriver_path', 'start_url']
    for param in required:
        if param not in config:
            raise ValueError(f"КРИТИЧЕСКАЯ ОШИБКА: Отсутствует обязательный параметр: {param} в config.txt")

    if 'firefox_binary' in config and config['firefox_binary']:
        options.binary_location = config['firefox_binary']

    if config.get('headless', 'true').lower() == 'true':
        options.add_argument("--headless")
        print("Запуск Firefox в headless режиме.")

    if config.get('load_images', 'true').lower() == 'false':
        options.set_preference("permissions.default.image", 2)
        print("Загрузка изображений отключена.")

    options.set_preference("dom.ipc.plugins.enabled.libflashplayer.so", False)
    options.set_preference("browser.cache.disk.enable", False)
    options.set_preference("browser.cache.memory.enable", False)
    options.set_preference("network.http.use-cache", False)

    log_path = os.devnull if config.get('disable_logs', 'false').lower() == 'true' else "geckodriver.log"
    if log_path == os.devnull:
        print("Логирование geckodriver отключено.")

    service = Service(
        executable_path=config['geckodriver_path'],
        log_path=log_path
    )

    try:
        print("Инициализация драйвера Firefox...")
        driver = webdriver.Firefox(service=service, options=options)
        print("Драйвер Firefox успешно инициализирован.")
        return driver
    except Exception as e:
        print(f"КРИТИЧЕСКАЯ ОШИБКА инициализации драйвера Firefox: {e}")
        print(f"Проверьте путь к geckodriver: {config.get('geckodriver_path')}")
        if 'firefox_binary' in config:
             print(f"Проверьте путь к бинарнику Firefox: {config.get('firefox_binary')}")
        raise

def main():
    driver = None
    try:
        start_time = time.time()
        print("Чтение конфигурационного файла...")
        config = read_config()
        print("Конфиг успешно загружен:")
        for key, value in config.items():
            print(f"  {key}: {value}") # Можно скрыть для краткости

        driver = configure_driver(config)

        helper = PageHelper(driver, wait_timeout=20) # Увеличено время ожидания
        start_url = config['start_url']
        print(f"\nЗагрузка стартовой страницы: {start_url}")
        driver.get(start_url)
        print("Страница загружена.")
        print(f"Заголовок страницы: {driver.title}")

        helper.wait_for_human_verification()

        if not helper.wait_for_container():
            print("КРИТИЧЕСКАЯ ОШИБКА: Не удалось обнаружить контейнер с меню навигации, завершаем работу.")
            return

        target_sections = [
            'Авиация',
            'Вертолёты',
            'Наземная техника',
            'Большой флот',
            'Малый флот'
        ]

        ## 1. Сбор данных из List View
        print("\n--- Начало сбора данных из List View ---")
        vehicles_data = []
        for section in target_sections:
            try:
                print(f"\nОбработка раздела (List View): {section}")
                nav_item = helper.wait.until(
                    EC.element_to_be_clickable(
                        (By.XPATH, f"//a[contains(@class, 'layout-nav_item')]//span[normalize-space(text())='{section}']/..")
                    )
                )
                nav_item.click()
                print(f"Переход в раздел '{section}' выполнен.")
                time.sleep(1.5) # Небольшая пауза

                list_button = helper.wait_for_id('wt-show-list')
                if list_button:
                    try:
                        # Прокрутка к кнопке перед кликом
                        driver.execute_script("arguments[0].scrollIntoView(true);", list_button)
                        #time.sleep(0.5)
                        helper.wait.until(EC.element_to_be_clickable(list_button)).click()
                    except Exception as e:
                        print(f"Предупреждение: Обычный клик по кнопке List не сработал: {e}. Пробую JS click.")
                        driver.execute_script("arguments[0].click();", list_button)
                    print("Кнопка 'List' активирована.")
                    #time.sleep(1.5) # Пауза для обновления

                    rows = helper.get_vehicle_rows()
                    total_rows = len(rows)
                    print(f"Найдено строк техники: {total_rows}")
                    processed_count = 0
                    for idx, row in enumerate(rows, start=1):
                        # print(f"Debug: Обработка строки {idx}/{total_rows}")
                        try:
                            data = helper.parse_vehicle_row(row, section)
                            if data is None:
                                continue

                            if data.get('silver') and str(data['silver']).isdigit() and int(data['silver']) > 0:
                                try:
                                     data = VehicleDataFetcher.fetch_required_exp(data)
                                except Exception as fetch_exp:
                                    print(f"Предупреждение: Не удалось получить required_exp для {data.get('name', data.get('data_ulist_id'))}: {fetch_exp}")

                            if data.get('silver'):
                                try:
                                    silver_str = str(data['silver']).replace(',', '').replace(' ', '').strip()
                                    if silver_str.isdigit():
                                         data['silver'] = int(silver_str)
                                    else:
                                         data['silver'] = None
                                except (ValueError, TypeError):
                                     print(f"Предупреждение: Не удалось конвертировать 'silver' в число для {data.get('name')}: '{data.get('silver')}'")
                                     data['silver'] = None

                            vehicles_data.append(data)
                            processed_count += 1
                        except Exception as e:
                            print(f"Ошибка при обработке строки {idx} в разделе '{section}' (List View): {e}")
                    print(f"Успешно обработано строк в разделе '{section}': {processed_count}/{total_rows}")
                else:
                    print(f"Предупреждение: Не удалось найти кнопку 'List' для раздела {section}")

            except TimeoutException as e:
                 print(f"Ошибка (тайм-аут) при обработке раздела '{section}' (List View): {e}")
            except Exception as e:
                print(f"Непредвиденная ошибка при обработке раздела '{section}' (List View): {e}")

        print(f"\n--- Сбор данных из List View завершен. Всего записей: {len(vehicles_data)} ---")
        save_to_csv(vehicles_data, filename="vehicles_list.csv")

        # 1.1 Сбор информации о странах
        print("\n--- Сбор информации о странах ---")
        country_images = {}
        if vehicles_data or target_sections: # Пытаемся собрать, даже если list view пуст
            first_section = target_sections[0] if target_sections else 'Авиация' # Запасной вариант
            try:
                print(f"Переход в раздел '{first_section}' для сбора информации о странах.")
                nav_item = helper.wait.until(
                    EC.element_to_be_clickable(
                        (By.XPATH, f"//a[contains(@class, 'layout-nav_item')]//span[normalize-space(text())='{first_section}']/..")
                    )
                )
                nav_item.click()
                time.sleep(1)

                # Ожидание появления блока с кнопками стран
                country_button_container = helper.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.unit-filter_country-buttons")))
                print("Блок кнопок стран найден.")
                time.sleep(0.5)

                country_images = helper.get_country_buttons()
                print(f"Собрано {len(country_images)} стран с флагами.")

            except Exception as e:
                print(f"Ошибка при сборе информации о странах в разделе '{first_section}': {e}")
        else:
             print("Нет данных List View и нет разделов, информация о странах не собиралась.")
        save_country_flags_to_csv(country_images, filename="country_flags.csv")

        ## 2. Сбор данных из Tree View
        print("\n--- Начало сбора данных из Tree View ---")
        tree_view_data_raw = []
        for section in target_sections:
            try:
                print(f"\nОбработка раздела (Tree View): {section}")
                nav_item = helper.wait.until(
                    EC.element_to_be_clickable(
                        (By.XPATH, f"//a[contains(@class, 'layout-nav_item')]//span[normalize-space(text())='{section}']/..")
                    )
                )
                nav_item.click()
                print(f"Переход в раздел '{section}' выполнен.")
                time.sleep(1.5) # Пауза

                tree_button = helper.wait.until(EC.presence_of_element_located((By.ID, "wt-show-tree")))
                try:
                     # Прокрутка к кнопке перед кликом
                     driver.execute_script("arguments[0].scrollIntoView(true);", tree_button)
                     time.sleep(0.5)
                     helper.wait.until(EC.element_to_be_clickable(tree_button)).click()
                except Exception as e:
                    print(f"Предупреждение: Обычный клик по кнопке Tree не сработал: {e}. Пробую JS click.")
                    driver.execute_script("arguments[0].click();", tree_button)
                print("Кнопка 'Tree' активирована.")
                time.sleep(2.5) # Пауза для загрузки дерева

                section_tree_data = get_all_nation_tree_data(helper, section)
                print(f"Собрано узлов из Tree View для раздела '{section}': {len(section_tree_data)}")
                tree_view_data_raw.extend(section_tree_data)

            except TimeoutException as e:
                 print(f"Ошибка (тайм-аут) при обработке раздела '{section}' (Tree View): {e}")
            except Exception as e:
                print(f"Непредвиденная ошибка при обработке раздела '{section}' (Tree View): {e}")

        print(f"\n--- Сбор сырых данных из Tree View завершен. Всего узлов: {len(tree_view_data_raw)} ---")
        save_to_csv(tree_view_data_raw, filename="vehicles_tree_raw.csv")

        ## 2.1 Фильтрация данных из Tree View
        print("\n--- Фильтрация данных из Tree View ---")
        time.sleep(20)
        # Шаг 1: Фильтруем ПАПКИ без имени
        filtered_tree_data_step1 = []
        folders_without_name_count = 0
        for node in tree_view_data_raw:
            if node.get('type') == 'folder' and not node.get('name'):
                folders_without_name_count += 1
                # print(f"Пропуск папки без имени: ID={node.get('data_ulist_id') or node.get('external_id')}")
                continue # Пропускаем папку без имени
            filtered_tree_data_step1.append(node)
        print(f"Узлов после фильтрации папок без имени: {len(filtered_tree_data_step1)} (удалено папок без имени: {folders_without_name_count})")

        # Шаг 2: Фильтруем ВСЕ узлы по уникальности ID
        unique_tree_data = []
        seen_ids = set()
        duplicates_count = 0
        nodes_without_id_count = 0
        for node in filtered_tree_data_step1:
            # Приоритет у data_ulist_id, если нет - external_id
            node_id = node.get('data_ulist_id') or node.get('external_id')

            if node_id:
                if node_id not in seen_ids:
                    unique_tree_data.append(node)
                    seen_ids.add(node_id)
                else:
                    duplicates_count += 1
                    # print(f"Пропуск дубликата по ID '{node_id}' для узла: {node.get('name')}")
            else:
                 nodes_without_id_count += 1
                 # print(f"Предупреждение: Узел пропущен при проверке уникальности из-за отсутствия ID: {node.get('name')}")

        print(f"Узлов после фильтрации по уникальности ID: {len(unique_tree_data)} (удалено дубликатов: {duplicates_count}, узлов без ID: {nodes_without_id_count})")

        # Сохраняем отфильтрованные данные Tree View
        save_to_csv(unique_tree_data, filename="vehicles_tree_filtered.csv")

        ## 3. Объединение данных и формирование зависимостей
        print("\n--- Объединение данных List View и отфильтрованных Tree View ---")
        merger = NodesMerger(vehicles_data, unique_tree_data)
        merged_data = merger.merge_data()
        print(f"Объединение завершено. Всего объединенных узлов: {len(merged_data)}")

        merged_fieldnames = [
            "data_ulist_id", "external_id", "link", "name", "country", "battle_rating",
            "silver", "rank", "vehicle_category", "type", "required_exp", "tech_category",
            "image_url", "parent_external_id", "column_index", "row_index", "order_in_folder"
        ]
        save_to_csv(merged_data, filename="vehicles_merged.csv", fieldnames=merged_fieldnames)

        print("\n--- Извлечение зависимостей ---")
        dependencies = merger.extract_node_dependencies(merged_data)
        print(f"Извлечено зависимостей: {len(dependencies)}")

        dep_fieldnames = ["node_external_id", "prerequisite_external_id"]
        save_dependencies_to_csv(dependencies, filename="dependencies.csv", fieldnames=dep_fieldnames)

        ## 4. Извлечение требований для открытия следующей эры (ранга)
        print("\n--- Шаг 4: Извлечение требований по рангам (пропущен) ---")
        # print("Извлекаем требования для открытия следующей эры для наций...")
        # try:
        #     run_rank_requirements_extraction()
        #     print("Сбор требований по рангам завершен.")
        # except NameError:
        #      print("Предупреждение: Функция run_rank_requirements_extraction не найдена. Пропуск шага.")
        # except Exception as e:
        #      print(f"Ошибка при сборе требований по рангам: {e}")
        rank_req_file = "rank_requirements.csv"
        if not os.path.exists(rank_req_file):
             try:
                 with open(rank_req_file, 'w', newline='') as f:
                     pass
                 print(f"Создан пустой файл '{rank_req_file}'.")
             except Exception as e:
                 print(f"Предупреждение: Не удалось создать пустой файл '{rank_req_file}': {e}")

        ## 5. Вставка извлеченных данных в БД
        print("\n--- Шаг 5: Загрузка данных в БД (пропущен) ---")
        print("Загрузка данных в БД...")
        try:
            upload_all_data(
                config=config,
                target_sections=target_sections,
                country_csv="country_flags.csv",
                merged_csv="vehicles_merged.csv",
                deps_csv="dependencies.csv",
                rank_csv=rank_req_file
            )
            print("Загрузка данных в БД успешно завершена.")
        except NameError:
             print("Предупреждение: Функция upload_all_data не найдена. Пропуск шага.")
        except Exception as e:
            print(f"Ошибка при загрузке данных в БД: {e}")


        end_time = time.time()
        elapse_time = end_time - start_time
        print(f"\nСкрипт успешно выполнился за: {elapse_time:.2f} сек. ({elapse_time / 60:.2f} мин.)")

    except Exception as e:
        # Используем print для вывода критических ошибок вместо logging.critical
        import traceback
        print(f"\nКРИТИЧЕСКАЯ ОШИБКА выполнения скрипта: {e}")
        print("Traceback:")
        print(traceback.format_exc())
    finally:
        if driver:
            try:
                driver.quit()
                print("Браузер закрыт.")
            except Exception as e:
                print(f"Ошибка при закрытии браузера: {e}")

if __name__ == "__main__":
    main()
    #config = read_config()
    #target_sections = [
    #        'Авиация', 
    #        'Вертолёты', 
    #        'Наземная техника',
    #        'Большой флот', 
    #        'Малый флот'
    #    ]
    #upload_all_data(
    #        config=config,
    #        target_sections=target_sections,
    #        country_csv="country_flags.csv",
    #        merged_csv="vehicles_merged.csv",
    #        deps_csv="dependencies.csv",
    #        rank_csv="rank_requirements.csv"
    #    )