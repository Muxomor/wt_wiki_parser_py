import re
from selenium.webdriver.common.by import By

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
        node = {}
        node['external_id'] = element.get_attribute("data-unit-id")
        # Сначала пробуем взять родительский идентификатор из data-unit-req
        node['parent_external_id'] = element.get_attribute("data-unit-req") or ""
        
        try:
            name_elem = element.find_element(By.CSS_SELECTOR, ".wt-tree_item-text span")
            node['name'] = name_elem.text.strip()
        except Exception as e:
            node['name'] = ""
            print(f"Ошибка при получении названия для {node.get('external_id')}: {e}")
        
        try:
            icon_elem = element.find_element(By.CLASS_NAME, "wt-tree_item-icon")
            style = icon_elem.get_attribute("style")
            node['image_url'] = extract_image_url(style)
        except Exception as e:
            node['image_url'] = ""
            print(f"Ошибка при получении image_url для {node.get('external_id')}: {e}")
        
        classes = element.get_attribute("class")
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
        except Exception as e:
            node['column_index'] = None
            node['row_index'] = None
            print(f"Ошибка при определении индексов для {node.get('external_id')}: {e}")
        
        try:
            parent_container = element.find_element(By.XPATH, "./ancestor::div[contains(@class, 'wt-tree_group-items')]")
            children = parent_container.find_elements(By.CSS_SELECTOR, "div.wt-tree_item")
            node['order_in_folder'] = children.index(element)
        except Exception as e:
            node['order_in_folder'] = None
    
        # Если у элемента есть order_in_folder (т.е. он внутри группы) и родительский идентификатор отсутствует,
        # ищем ближайший родительский элемент с классом wt-tree_group и берем его data-unit-id
        if node.get('order_in_folder') is not None and not node['parent_external_id']:
            try:
                parent_group = element.find_element(By.XPATH, "./ancestor::div[contains(@class, 'wt-tree_group')]")
                if parent_group:
                    parent_id = parent_group.get_attribute("data-unit-id")
                    node['parent_external_id'] = parent_id or ""
            except Exception as e:
                print(f"Не удалось определить родительскую группу для {node.get('external_id')}: {e}")
        
        return node

    def extract_folder_node(self, folder_element):
        node = {}
        ext_id = folder_element.get_attribute("data-unit-id")
        try:
            name_elem = folder_element.find_element(By.CSS_SELECTOR, ".wt-tree_group-folder_inner .wt-tree_item-text span")
            name = name_elem.text.strip()
        except Exception as e:
            name = ""
            print(f"Ошибка при получении названия папки: {e}")
        # Если отсутствует data-unit-id, создаем его на основе названия
        if not ext_id:
            ext_id = name.lower().replace(" ", "_") + "_group"
        node['external_id'] = ext_id
        node['parent_external_id'] = folder_element.get_attribute("data-unit-req")
        node['type'] = "folder"
        node['name'] = name
        try:
            icon_elem = folder_element.find_element(By.CSS_SELECTOR, ".wt-tree_group-folder_inner .wt-tree_item-icon")
            style = icon_elem.get_attribute("style")
            node['image_url'] = extract_image_url(style)
        except Exception as e:
            node['image_url'] = ""
            print(f"Ошибка при получении image_url для папки {ext_id}: {e}")
        node['tech_category'] = "standard"
        # Попытка вычислить индексы через таблицу
        try:
            tbody = folder_element.find_element(By.XPATH, "./ancestor::tbody[1]")
            trs = tbody.find_elements(By.XPATH, "./tr")
            tr = folder_element.find_element(By.XPATH, "./ancestor::tr[1]")
            node['row_index'] = trs.index(tr)
            tds = tr.find_elements(By.XPATH, "./td")
            td = folder_element.find_element(By.XPATH, "./ancestor::td[1]")
            node['column_index'] = tds.index(td)
        except Exception as e:
            # Если не удалось, определим индексы по порядку среди всех групповых узлов
            try:
                all_folders = self.driver.find_elements(By.CSS_SELECTOR, "div.wt-tree_group, div.wt-tree_group-folder")
                node['row_index'] = 0  # Поскольку группы могут не иметь строковой организации, зададим 0
                node['column_index'] = all_folders.index(folder_element)
            except Exception as ex:
                node['row_index'] = None
                node['column_index'] = None
                print(f"Не удалось вычислить индексы для группового узла {ext_id}: {ex}")
        try:
            # Порядок среди групповых узлов
            all_folders = self.driver.find_elements(By.CSS_SELECTOR, "div.wt-tree_group, div.wt-tree_group-folder")
            node['order_in_folder'] = all_folders.index(folder_element)
        except Exception as e:
            node['order_in_folder'] = None
            print(f"Не удалось определить порядок для группового узла {ext_id}: {e}")
        print(f"Извлечена группа: external_id={node.get('external_id')}, name={node.get('name')}, row_index={node.get('row_index')}, column_index={node.get('column_index')}, order_in_folder={node.get('order_in_folder')}")
        return node

    def extract_nodes(self):
        nodes = []
        vehicle_elements = self.driver.find_elements(By.CSS_SELECTOR, "div.wt-tree_item")
        for elem in vehicle_elements:
            try:
                node = self.extract_vehicle_node(elem)
                nodes.append(node)
            except Exception as e:
                print(f"Ошибка при обработке vehicle узла: {e}")
        folder_elements = self.driver.find_elements(By.CSS_SELECTOR, "div.wt-tree_group, div.wt-tree_group-folder")
        for folder in folder_elements:
            try:
                node = self.extract_folder_node(folder)
                nodes.append(node)
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
