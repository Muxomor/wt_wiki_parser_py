import re
from selenium.webdriver.common.by import By

class TreeDataExtractor:
    def __init__(self, helper):
        """
        :param helper: экземпляр PageHelper, через который получаем доступ к driver
        """
        self.helper = helper
        self.driver = helper.driver

    def _get_cell_indexes(self, element):
        """
        Вычисляет column_index и row_index для элемента, основываясь на его расположении внутри TD и TR.
        Возвращает кортеж (column_index, row_index) или (None, None), если не удалось определить.
        """
        try:
            # Находим ближайший родительский TD
            td = element.find_element(By.XPATH, "./ancestor::td[1]")
            # Получаем индекс TD среди всех TD в родительской строке
            tr = td.find_element(By.XPATH, "./ancestor::tr[1]")
            tds = tr.find_elements(By.XPATH, "./td")
            column_index = tds.index(td)
            # Теперь получаем индекс строки внутри родительского tbody
            tbody = tr.find_element(By.XPATH, "./ancestor::tbody[1]")
            trs = tbody.find_elements(By.XPATH, "./tr")
            row_index = trs.index(tr)
            return column_index, row_index
        except Exception as e:
            print(f"Ошибка при определении cell indexes: {e}")
            return None, None

    def _get_order_in_folder(self, element):
        """
        Если элемент находится внутри контейнера с классом wt-tree_group-items (папка),
        вычисляет его порядковый номер среди дочерних узлов.
        Если не найден родитель, возвращает None.
        """
        try:
            parent_container = element.find_element(By.XPATH, "./ancestor::div[contains(@class, 'wt-tree_group-items')]")
            children = parent_container.find_elements(By.CSS_SELECTOR, "div.wt-tree_item")
            return children.index(element)
        except Exception as e:
            # Если элемент не принадлежит папке, вернем None
            return None

    def extract_vehicle_node(self, element):
        """
        Извлекает данные для стандартного узла техники (vehicle).
        Добавляются параметры: column_index, row_index и order_in_folder (если применимо).
        """
        node = {}
        node['external_id'] = element.get_attribute("data-unit-id")
        node['parent_external_id'] = element.get_attribute("data-unit-req")
        
        # Название
        try:
            name_elem = element.find_element(By.CSS_SELECTOR, ".wt-tree_item-text span")
            node['name'] = name_elem.text.strip()
        except Exception as e:
            node['name'] = ""
            print(f"Ошибка при получении названия для {node.get('external_id')}: {e}")
        
        # Извлечение image_url из background-image
        try:
            icon_elem = element.find_element(By.CSS_SELECTOR, ".wt-tree_item-icon")
            style = icon_elem.get_attribute("style")
            match = re.search(r"url\('([^']+)'\)", style)
            node['image_url'] = match.group(1) if match else ""
        except Exception as e:
            node['image_url'] = ""
            print(f"Ошибка при получении image_url для {node.get('external_id')}: {e}")
        
        # Определяем tech_category по наличию класса (wt-tree_item--prem → premium, иначе standard)
        classes = element.get_attribute("class")
        node['tech_category'] = "premium" if "wt-tree_item--prem" in classes else "standard"
        node['type'] = "vehicle"
        
        # Вычисляем column_index и row_index (если возможно)
        col_idx, row_idx = self._get_cell_indexes(element)
        node['column_index'] = col_idx
        node['row_index'] = row_idx
        
        # Если элемент находится в папке, вычисляем порядок внутри неё
        node['order_in_folder'] = self._get_order_in_folder(element)
        return node

    def extract_folder_node(self, folder_element):
        """
        Извлекает данные для узла-папки.
        Папка определяется по контейнеру с классом wt-tree_group.
        """
        node = {}
        node['external_id'] = folder_element.get_attribute("data-unit-id")
        node['parent_external_id'] = folder_element.get_attribute("data-unit-req")
        node['type'] = "folder"
        
        try:
            name_elem = folder_element.find_element(By.CSS_SELECTOR, ".wt-tree_group-folder_inner .wt-tree_item-text span")
            node['name'] = name_elem.text.strip()
        except Exception as e:
            node['name'] = ""
            print(f"Ошибка при получении названия папки {node.get('external_id')}: {e}")
        
        try:
            icon_elem = folder_element.find_element(By.CSS_SELECTOR, ".wt-tree_group-folder_inner .wt-tree_item-icon")
            style = icon_elem.get_attribute("style")
            match = re.search(r"url\('([^']+)'\)", style)
            node['image_url'] = match.group(1) if match else ""
        except Exception as e:
            node['image_url'] = ""
            print(f"Ошибка при получении image_url для папки {node.get('external_id')}: {e}")
        
        node['tech_category'] = "standard"
        # Для папок визуальные индексы могут быть неактуальны – оставляем None
        node['column_index'] = None
        node['row_index'] = None
        node['order_in_folder'] = None
        return node

    def extract_nodes(self):
        """
        Извлекает все узлы (как vehicle, так и folder) со страницы Tree.
        Возвращает список словарей, где каждый словарь содержит:
            - external_id
            - parent_external_id
            - name
            - image_url
            - tech_category
            - type ("vehicle" или "folder")
            - column_index, row_index (позиция в таблице) – для vehicle узлов
            - order_in_folder – для узлов, находящихся внутри папок (если применимо)
        """
        nodes = []
        # Извлекаем все vehicle узлы
        vehicle_elements = self.driver.find_elements(By.CSS_SELECTOR, "div.wt-tree_item")
        for elem in vehicle_elements:
            try:
                node = self.extract_vehicle_node(elem)
                nodes.append(node)
            except Exception as e:
                print(f"Ошибка при обработке vehicle узла: {e}")
        
        # Извлекаем все folder узлы
        folder_elements = self.driver.find_elements(By.CSS_SELECTOR, "div.wt-tree_group")
        for folder in folder_elements:
            try:
                node = self.extract_folder_node(folder)
                nodes.append(node)
                # Если внутри папки есть дочерние узлы, извлекаем их
                try:
                    child_elements = folder.find_elements(By.CSS_SELECTOR, "div.wt-tree_group-items div.wt-tree_item")
                    for child in child_elements:
                        child_node = self.extract_vehicle_node(child)
                        if not child_node.get("parent_external_id"):
                            child_node["parent_external_id"] = node["external_id"]
                        nodes.append(child_node)
                except Exception as ce:
                    print(f"Ошибка при обработке дочерних узлов папки {node['external_id']}: {ce}")
            except Exception as e:
                print(f"Ошибка при обработке folder узла: {e}")
        return nodes
