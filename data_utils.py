import csv
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from tree_data_extractor import TreeDataExtractor

def save_to_csv(data_list, filename="vehicles.csv", fieldnames=None):
    """Сохраняет список словарей в CSV файл."""
    if not data_list:
        print(f"Нет данных для сохранения в {filename}.")
        return
    if not isinstance(data_list, list) or not isinstance(data_list[0], dict):
         print(f"Ошибка: Ожидался список словарей для сохранения в {filename}, получен {type(data_list)}.")
         return

    if not fieldnames:
        fieldnames = list(data_list[0].keys())

    try:
        with open(filename, "w", newline="", encoding="utf-8") as f:
            dict_writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore', restval='')
            dict_writer.writeheader()
            dict_writer.writerows(data_list)
        print(f"Данные ({len(data_list)} строк) сохранены в {filename}")
    except Exception as e:
        print(f"Ошибка при сохранении данных в CSV {filename}: {e}")


def roman_to_int(s: str) -> int:
    """
    Конвертирует римские цифры (I, II, IV и т.д.) в целые числа.
    """
    roman_map = {'I': 1, 'V': 5, 'X': 10, 'L': 50,
                 'C': 100, 'D': 500, 'M': 1000}
    total, prev = 0, 0
    for ch in reversed(s.upper()):
        val = roman_map.get(ch, 0)
        if val < prev:
            total -= val
        else:
            total += val
            prev = val
    return total

def save_country_flags_to_csv(country_images, filename="country_flags.csv"):
    """
    Сохраняет информацию о странах и URL флагов в CSV-файл.
    """
    import csv
    if not country_images:
         print(f"Нет данных о флагах стран для сохранения в {filename}.")
         return
    try:
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["country", "flag_image_url"])
            for country, image_url in country_images.items():
                writer.writerow([country, image_url])
        print(f"Информация о странах ({len(country_images)} записей) сохранена в файл {filename}")
    except Exception as e:
        print(f"Ошибка при сохранении информации о странах: {e}")


def save_dependencies_to_csv(dependencies, filename="dependencies.csv", fieldnames=None):
    """Сохраняет зависимости узлов в CSV файл."""
    if not dependencies:
        print(f"Нет зависимостей для сохранения в {filename}.")
        return
    if not fieldnames:
        fieldnames = ["node_external_id", "prerequisite_external_id"]
    try:
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore', restval='')
            writer.writeheader()
            writer.writerows(dependencies)
        print(f"Зависимости ({len(dependencies)} строк) сохранены в {filename}")
    except Exception as e:
         print(f"Ошибка при сохранении зависимостей в CSV {filename}: {e}")


def get_all_nation_tree_data(helper, target_section):
    """
    Собирает все узлы (техника и папки) из Tree View для всех наций в текущем разделе.
    """
    all_nodes_in_section = []
    try:
        container = helper.wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.navtabs_wrapper"))
        )
        nation_tabs = container.find_elements(By.CSS_SELECTOR, "div.navtabs_item")
        print(f"Найдено вкладок наций в разделе '{target_section}': {len(nation_tabs)}")

        if not nation_tabs:
             print(f"Вкладки наций не найдены в разделе '{target_section}'.")
             return []

        extractor = TreeDataExtractor(helper)

        for i, tab in enumerate(nation_tabs):
            nation_label = ""
            try:
                helper.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center', inline: 'center'});", tab
                )
                time.sleep(0.5)

                try:
                    label_element = tab.find_element(By.CSS_SELECTOR, "div.navtabs_item-label")
                    nation_label = label_element.text.strip()
                except Exception:
                    nation_label = f"[вкладка {i+1}]"

                print(f"Обработка нации: {nation_label} (вкладка {i+1}/{len(nation_tabs)}) в разделе '{target_section}'")

                try:
                    helper.wait.until(EC.element_to_be_clickable(tab)).click()
                except Exception as e:
                    print(f"Предупреждение: Обычный клик по вкладке '{nation_label}' не сработал ({e}). Пробую JS click.")
                    try:
                        helper.driver.execute_script("arguments[0].click();", tab)
                    except Exception as js_e:
                        print(f"JS click по вкладке '{nation_label}' также не удался: {js_e}. Пропускаем нацию.")
                        continue

                time.sleep(2.5)

                nation_data = extractor.extract_nodes()
                print(f"Извлечено {len(nation_data)} узлов для нации '{nation_label}'.")
                all_nodes_in_section.extend(nation_data)

            except Exception as tab_e:
                print(f"Ошибка при обработке вкладки нации '{nation_label}' в разделе '{target_section}': {tab_e}")
                try:
                    helper.driver.execute_script("arguments[0].scrollLeft += 200;", container)
                    time.sleep(0.5)
                except Exception as scroll_e:
                    print(f"Ошибка при попытке прокрутки контейнера вкладок после ошибки: {scroll_e}")
                continue

    except TimeoutException:
        print(f"Не удалось найти контейнер с вкладками наций ('div.navtabs_wrapper') в разделе '{target_section}'.")
    except Exception as e:
        print(f"Общая ошибка при получении данных дерева для раздела '{target_section}': {e}")

    print(f"Сбор данных TreeView для раздела '{target_section}' завершен. Собрано узлов: {len(all_nodes_in_section)}.")
    return all_nodes_in_section