import csv
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

def save_to_csv(data_list, filename="vehicles.csv", fieldnames=None):
    if not data_list:
        print("Нет данных для сохранения.")
        return
    if not fieldnames:
        fieldnames = [
            "data_ulist_id", "external_id", "link", "name", "country", "battle_rating",
            "silver", "rank", "vehicle_category", "type", "required_exp",
            "image_url", "parent_external_id", "column_index", "row_index", "order_in_folder"
        ]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        dict_writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        dict_writer.writeheader()
        dict_writer.writerows(data_list)
    print(f"Данные сохранены в {filename}")

def save_country_flags_to_csv(country_images, filename="country_flags.csv"):
    """
    Сохраняет информацию о странах и URL флагов в CSV-файл.
    
    :param country_images: Словарь вида {country: flag_image_url}
    :param filename: Имя файла для сохранения
    """
    import csv
    try:
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["country", "flag_image_url"])
            for country, image_url in country_images.items():
                writer.writerow([country, image_url])
        print(f"Информация о странах сохранена в файл {filename}")
    except Exception as e:
        print(f"Ошибка при сохранении информации о странах: {e}")


def save_dependencies_to_csv(dependencies, filename="dependencies.csv", fieldnames=None):
    if not dependencies:
        print("Нет зависимостей для сохранения.")
        return
    if not fieldnames:
        fieldnames = ["node_external_id", "prerequisite_external_id"]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(dependencies)
    print(f"Зависимости сохранены в {filename}")

def get_all_nation_tree_data(helper, target_section):
    nation_tree_data = {}
    try:
        container = helper.driver.find_element(By.CSS_SELECTOR, "div.navtabs_wrapper")
        nation_tabs = container.find_elements(By.CSS_SELECTOR, "div.navtabs_item")
        print(f"Найдено вкладок наций: {len(nation_tabs)}")
        
        # Обрабатываем только первую вкладку, вместо перебора всех
        if nation_tabs:
            tab = nation_tabs[0]
            nation_label = ""
            try:
                helper.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center', inline: 'center'});", tab
                )
                #time.sleep(0.5)
                try:
                    nation_label = tab.find_element(By.CSS_SELECTOR, "div.navtabs_item-label").text.strip()
                except Exception as e:
                    nation_label = ""
                    print("Не удалось получить название вкладки:", e)
                print(f"Собираем данные для нации: {nation_label if nation_label else '[без названия]'}")
                try:
                    tab.click()
                except Exception as e:
                    print("Ошибка клика по вкладке, пробую JS click.")
                    helper.driver.execute_script("arguments[0].click();", tab)
                time.sleep(20)
                from tree_data_extractor import TreeDataExtractor
                extractor = TreeDataExtractor(helper)
                nation_data = extractor.extract_nodes()
                print(f"Извлечено {len(nation_data)} узлов для нации {nation_label} в разделе {target_section}")
                for node in nation_data:
                    ext_id = node.get("external_id")
                    if ext_id and ext_id not in nation_tree_data:
                        nation_tree_data[ext_id] = node
            except Exception as ne:
                print(f"Ошибка при обработке нации '{nation_label}': {ne}")
                try:
                    helper.driver.execute_script("arguments[0].scrollLeft += 200;", container)
                    #time.sleep(1)
                except Exception as se:
                    print(f"Ошибка при прокрутке контейнера: {se}")
        
        # Исходный цикл по всем вкладкам наций закомментирован:
        # for tab in nation_tabs:
        #     nation_label = ""
        #     try:
        #         helper.driver.execute_script(
        #             "arguments[0].scrollIntoView({block: 'center', inline: 'center'});", tab
        #         )
        #         #time.sleep(0.5)
        #         try:
        #             nation_label = tab.find_element(By.CSS_SELECTOR, "div.navtabs_item-label").text.strip()
        #         except Exception as e:
        #             nation_label = ""
        #             print("Не удалось получить название вкладки:", e)
        #         print(f"Собираем данные для нации: {nation_label if nation_label else '[без названия]'}")
        #         try:
        #             tab.click()
        #         except Exception as e:
        #             print("Ошибка клика по вкладке, пробую JS click.")
        #             helper.driver.execute_script("arguments[0].click();", tab)
        #         #time.sleep(2)
        #         from tree_data_extractor import TreeDataExtractor
        #         extractor = TreeDataExtractor(helper)
        #         nation_data = extractor.extract_nodes()
        #         print(f"Извлечено {len(nation_data)} узлов для нации {nation_label} в разделе {target_section}")
        #         for node in nation_data:
        #             ext_id = node.get("external_id")
        #             if ext_id and ext_id not in nation_tree_data:
        #                 nation_tree_data[ext_id] = node
        #     except Exception as ne:
        #         print(f"Ошибка при обработке нации '{nation_label}': {ne}")
        #         try:
        #             helper.driver.execute_script("arguments[0].scrollLeft += 200;", container)
        #             #time.sleep(1)
        #         except Exception as se:
        #             print(f"Ошибка при прокрутке контейнера: {se}")
        #         continue
    except Exception as e:
        print(f"Ошибка при получении вкладок наций: {e}")
    return list(nation_tree_data.values())