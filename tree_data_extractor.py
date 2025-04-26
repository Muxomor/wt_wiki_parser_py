import re
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException # Добавлен импорт

def extract_image_url(style):
    """
    Извлекает URL из строки вида: background-image:url('https://...') или background-image:url("https://...")
    """
    match = re.search(r"url\(['\"]?([^'\")]+)['\"]?\)", style)
    return match.group(1) if match else ""

class TreeDataExtractor:
    def __init__(self, helper):
        """
        :param helper: экземпляр PageHelper для доступа к driver
        """
        self.helper = helper
        self.driver = helper.driver

    def extract_vehicle_node(self, element):
        """Извлекает данные для узла техники."""
        node = {}
        node['data_ulist_id'] = element.get_attribute("data-ulist-id")
        node['external_id'] = element.get_attribute("data-unit-id")

        # --- Гарантируем наличие обоих ID, используя один из них как запасной ---
        if not node['data_ulist_id'] and node['external_id']:
             node['data_ulist_id'] = node['external_id']
        elif not node['external_id'] and node['data_ulist_id']:
             node['external_id'] = node['data_ulist_id']
        elif not node['data_ulist_id'] and not node['external_id']:
             # Это не должно происходить для техники, но на всякий случай
             print(f"КРИТИЧЕСКОЕ ПРЕДУПРЕЖДЕНИЕ: Узел техники не имеет ни data-ulist-id, ни data-unit-id!")
             # Попытка извлечь имя для идентификации
             try:
                  name_elem = element.find_element(By.CSS_SELECTOR, ".wt-tree_item-text span")
                  print(f"   Проблемный узел (возможно): {name_elem.text.strip()}")
             except:
                  print(f"   Проблемный узел без имени и ID.")
             return None # Пропускаем узел без ID

        # --- Получаем parent_external_id из data-unit-req (если есть) ---
        node['parent_external_id'] = element.get_attribute("data-unit-req") or ""
        has_req_parent = bool(node['parent_external_id']) # Запоминаем, был ли родитель из data-unit-req

        # --- Получаем остальные атрибуты ---
        try:
            name_elem = element.find_element(By.CSS_SELECTOR, ".wt-tree_item-text span")
            node['name'] = name_elem.text.strip()
        except Exception:
            node['name'] = ""

        try:
            icon_elem = element.find_element(By.CLASS_NAME, "wt-tree_item-icon")
            style = icon_elem.get_attribute("style")
            node['image_url'] = extract_image_url(style)
        except Exception:
            node['image_url'] = ""

        classes = element.get_attribute("class") or ""
        node['tech_category'] = "premium" if "wt-tree_item--prem" in classes else "standard"
        node['type'] = "vehicle"

        try:
            td = element.find_element(By.XPATH, "./ancestor::td[1]")
            tr = td.find_element(By.XPATH, "./ancestor::tr[1]")
            tds = tr.find_elements(By.XPATH, "./td")
            node['column_index'] = tds.index(td)
            tbody = tr.find_element(By.XPATH, "./ancestor::tbody[1]")
            trs = tbody.find_elements(By.XPATH, "./tr")
            node['row_index'] = trs.index(tr)
        except Exception:
            node['column_index'] = None
            node['row_index'] = None

        # --- Определяем order_in_folder и родителя из группы (если применимо) ---
        node['order_in_folder'] = None # По умолчанию None
        try:
            # Ищем контейнер родительской группы items
            parent_container = element.find_element(By.XPATH, "./ancestor::div[contains(@class, 'wt-tree_group-items')][1]")
            # Находим непосредственных детей-элементов внутри этого контейнера
            children_in_group = parent_container.find_elements(By.CSS_SELECTOR, ":scope > div.wt-tree_item")
            if element in children_in_group:
                 node['order_in_folder'] = children_in_group.index(element)
                 # print(f"Debug: Узел {node.get('external_id')} найден внутри группы, order={node['order_in_folder']}")

                 # Если узел в группе И у него НЕ БЫЛО родителя из data-unit-req, ищем ID самой группы
                 if not has_req_parent:
                      # print(f"Debug: У узла {node.get('external_id')} нет data-unit-req, ищем ID родительской группы...")
                      try:
                           # Ищем сам элемент группы, который содержит parent_container
                           parent_group_element = parent_container.find_element(By.XPATH, "./ancestor::div[contains(@class, 'wt-tree_group')][1]")
                           parent_ulist_id = parent_group_element.get_attribute("data-ulist-id")
                           parent_unit_id = parent_group_element.get_attribute("data-unit-id")
                           parent_id_from_group = parent_ulist_id or parent_unit_id # Приоритет ulist_id

                           if parent_id_from_group:
                                node['parent_external_id'] = parent_id_from_group
                                # print(f"Debug: ---> Назначен родитель из группы: {parent_id_from_group} для узла {node.get('external_id')}")
                           else:
                                print(f"Предупреждение: Родительская группа для узла {node.get('external_id')} не имеет ID (ulist или unit).")
                                node['parent_external_id'] = "" # Оставляем пустым

                      except NoSuchElementException:
                           print(f"Предупреждение: Не найден элемент родительской группы для узла {node.get('external_id')}, хотя он в 'group-items'.")
                           node['parent_external_id'] = ""
                      except Exception as e_parent:
                           print(f"Ошибка при поиске ID родительской группы для {node.get('external_id')}: {e_parent}")
                           node['parent_external_id'] = ""
                 # else:
                      # print(f"Debug: У узла {node.get('external_id')} уже есть родитель из data-unit-req: {node['parent_external_id']}")

        except NoSuchElementException:
             # Если не найден 'wt-tree_group-items', значит узел не в папке
             node['order_in_folder'] = None
             # print(f"Debug: Узел {node.get('external_id')} не находится внутри 'wt-tree_group-items'.")
        except Exception as e_order:
             print(f"Ошибка при определении порядка/родителя в группе для {node.get('external_id')}: {e_order}")
             node['order_in_folder'] = None
             # Если была ошибка здесь, но родитель был из data-unit-req, он сохранится.
             # Если не было, то останется пустым.

        # Финальный print для отладки узла
        # print(f"Извлечен узел техники: id={node.get('data_ulist_id')}, ext_id={node.get('external_id')}, name='{node.get('name')}', parent='{node.get('parent_external_id')}', type={node.get('type')}, coords=({node.get('row_index')}, {node.get('column_index')}, {node.get('order_in_folder')})")
        return node

    def extract_folder_node(self, folder_element):
        """Извлекает данные для узла-папки."""
        node = {}
        node['data_ulist_id'] = folder_element.get_attribute("data-ulist-id")
        node['external_id'] = folder_element.get_attribute("data-unit-id")

        name = ""
        try:
            name_elem = folder_element.find_element(By.CSS_SELECTOR, ".wt-tree_group-folder_inner .wt-tree_item-text span")
            name = name_elem.text.strip()
            node['name'] = name
        except Exception:
             node['name'] = ""
             print(f"Предупреждение: Не удалось извлечь имя для папки с ID: ulist='{node['data_ulist_id']}', unit='{node['external_id']}'")


        # --- Гарантируем наличие обоих ID ---
        if not node['data_ulist_id'] and node['external_id']:
            node['data_ulist_id'] = node['external_id']
        elif not node['external_id'] and node['data_ulist_id']:
             node['external_id'] = node['data_ulist_id']
        elif not node['data_ulist_id'] and not node['external_id']:
             gen_id = name.lower().replace(" ", "_") + "_group" if name else "unknown_folder_group"
             node['data_ulist_id'] = gen_id
             node['external_id'] = gen_id
             print(f"Предупреждение: Сгенерирован ID '{gen_id}' для папки без ID с именем '{name}'")


        node['parent_external_id'] = folder_element.get_attribute("data-unit-req") or ""
        node['type'] = "folder"
        node['tech_category'] = "standard"

        try:
            icon_elem = folder_element.find_element(By.CSS_SELECTOR, ".wt-tree_group-folder_inner .wt-tree_item-icon")
            style = icon_elem.get_attribute("style")
            node['image_url'] = extract_image_url(style)
        except Exception:
            node['image_url'] = ""

        # Вычисление индексов через таблицу
        try:
            td = folder_element.find_element(By.XPATH, "./ancestor::td[1]")
            tr = td.find_element(By.XPATH, "./ancestor::tr[1]")
            tds = tr.find_elements(By.XPATH, "./td")
            node['column_index'] = tds.index(td)
            tbody = tr.find_element(By.XPATH, "./ancestor::tbody[1]")
            trs = tbody.find_elements(By.XPATH, "./tr")
            node['row_index'] = trs.index(tr)
        except Exception:
            node['row_index'] = None
            node['column_index'] = None

        # Для папок order_in_folder не имеет смысла (они не *внутри* другой папки)
        node['order_in_folder'] = None

        # print(f"Извлечена папка: id={node.get('data_ulist_id')}, ext_id={node.get('external_id')}, name='{node.get('name')}', parent='{node.get('parent_external_id')}', type={node.get('type')}, coords=({node.get('row_index')}, {node.get('column_index')}, {node.get('order_in_folder')})")
        return node

    def extract_nodes(self):
        """Извлекает все узлы (техника и папки) из текущего дерева."""
        nodes = []
        processed_ids = set() # Отслеживаем ID, чтобы не добавлять дубликаты

        # Сначала обрабатываем все элементы техники (div.wt-tree_item)
        vehicle_elements = self.driver.find_elements(By.CSS_SELECTOR, "div.wt-tree_item")
        # print(f"Найдено {len(vehicle_elements)} элементов div.wt-tree_item")
        for elem in vehicle_elements:
            try:
                # print(f"Обработка vehicle_element с data-unit-id={elem.get_attribute('data-unit-id')}")
                node = self.extract_vehicle_node(elem)
                if node: # extract_vehicle_node может вернуть None, если нет ID
                    node_id = node.get('data_ulist_id') # Используем data_ulist_id как основной ID
                    if node_id and node_id not in processed_ids:
                         nodes.append(node)
                         processed_ids.add(node_id)
                         print(f"Добавлен узел техники: {node_id}")
                    elif node_id in processed_ids:
                         print(f"Пропущен дубликат узла техники: {node_id}")
                    elif not node_id: # Эта проверка теперь внутри extract_vehicle_node
                         print(f"Пропущен узел техники без ID.")
                         pass

            except Exception as e:
                print(f"КРИТИЧЕСКАЯ ОШИБКА при обработке узла техники: {e}")

        # Затем обрабатываем все элементы папок (div.wt-tree_group)
        folder_elements = self.driver.find_elements(
            By.CSS_SELECTOR,
            "div.wt-tree_group[data-unit-id], div.wt-tree_group[data-ulist-id]"
        )
        # print(f"Найдено {len(folder_elements)} элементов div.wt-tree_group")
        for folder in folder_elements:
             try:
                 # print(f"Обработка folder_element с data-unit-id={folder.get_attribute('data-unit-id')}")
                 node = self.extract_folder_node(folder)
                 if node:
                    node_id = node.get('data_ulist_id') # Используем data_ulist_id как основной ID
                    if node_id and node_id not in processed_ids:
                         nodes.append(node)
                         processed_ids.add(node_id)
                         print(f"Добавлена папка: {node_id}")
                    elif node_id in processed_ids:
                         print(f"Пропущена дубликат папки: {node_id}")
                    elif not node_id:
                         print(f"Пропущена папка без ID.")
                         pass
             except Exception as e:
                  print(f"КРИТИЧЕСКАЯ ОШИБКА при обработке узла папки: {e}")

        print(f"Экстрактор извлек {len(nodes)} уникальных узлов.")
        return nodes