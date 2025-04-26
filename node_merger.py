import logging # Добавим импорт logging для возможного вывода предупреждений

# Настройка базового логирования (опционально, но полезно для отладки)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class NodesMerger:
    """
    Объединяет данные узлов из двух различных представлений (List View и Tree View) в единую структуру.

    Этот класс принимает два списка словарей, представляющих данные узлов, и выполняет слияние
    на основе идентификаторов ('data_ulist_id' или 'external_id'). Он также обрабатывает
    иерархические связи ('parent_external_id') и заполняет недостающие атрибуты
    в групповых узлах ('folder') на основе данных их дочерних узлов.

    Атрибуты:
        list_view_data (list): Список словарей из List View. Ожидается наличие ключа 'data_ulist_id' или 'external_id'.
        tree_view_data (list): Список словарей из Tree View. Ожидается наличие ключа 'external_id',
                               а также могут присутствовать 'parent_external_id', данные о позиционировании
                               ('column_index', 'row_index', 'order_in_folder'), 'image_url', 'type', 'tech_category'.
    """
    def __init__(self, list_view_data, tree_view_data):
        """
        Инициализирует NodesMerger с данными из List View и Tree View.

        :param list_view_data: Список словарей из List View.
        :param tree_view_data: Список словарей из Tree View.
        """
        self.list_view_data = list_view_data if list_view_data is not None else []
        self.tree_view_data = tree_view_data if tree_view_data is not None else []
        logging.info(f"Инициализация NodesMerger с {len(self.list_view_data)} элементами List View и {len(self.tree_view_data)} элементами Tree View.")

    def merge_data(self):
        """
        Выполняет слияние данных из list_view_data и tree_view_data.

        Процесс слияния:
        1. Создает словарь merged_dict, используя 'data_ulist_id' (или 'external_id') из list_view_data в качестве ключей.
        2. Обновляет/дополняет записи в merged_dict данными из tree_view_data, сопоставляя по 'external_id'.
           - Пропускает узлы с некорректным external_id ('_group').
           - Обновляет поля: 'image_url', 'parent_external_id', 'column_index', 'row_index', 'order_in_folder', 'type', 'tech_category'.
           - Устанавливает значения по умолчанию для 'type' ('vehicle') и 'tech_category' ('standard'), если они отсутствуют.
        3. Гарантирует, что каждый узел в merged_dict имеет ключ 'data_ulist_id', используя 'external_id', если необходимо.
        4. Преобразует merged_dict обратно в список merged_data.
        5. Обрабатывает групповые узлы ('folder'):
           - Устанавливает виртуальные 'row_index', 'column_index', 'order_in_folder', если они отсутствуют.
           - Заполняет отсутствующие 'rank', 'country', 'vehicle_category' у папок на основе данных дочерних узлов.
             - 'rank' берется из первого дочернего узла, у которого 'order_in_folder' не None и >= 0.
             - 'country' и 'vehicle_category' берутся из первого найденного дочернего узла.

        :return: Список словарей с объединенными и обработанными данными узлов.
        :rtype: list[dict]
        """
        merged_dict = {}
        # 1. Заполнение из List View
        for item in self.list_view_data:
            key = item.get('data_ulist_id') or item.get('external_id')
            if key:
                merged_dict[key] = item
            else:
                logging.warning(f"Элемент в list_view_data пропущен из-за отсутствия 'data_ulist_id' и 'external_id': {item}")


        # 2. Объединение с данными из Tree View
        for tree_node in self.tree_view_data:
            ext_id = tree_node.get('external_id')
            if not ext_id:
                logging.warning(f"Узел в tree_view_data пропущен из-за отсутствия 'external_id': {tree_node}")
                continue
            # Пропускаем узлы с некорректным идентификатором
            if ext_id == "_group":
                logging.info(f"Узел с external_id='_group' пропущен: {tree_node}")
                continue

            if ext_id in merged_dict:
                # Обновляем существующую запись
                merged_node = merged_dict[ext_id]
                merged_node.update({
                    # Обновляем image_url, только если он есть в tree_node, иначе оставляем существующий
                    'image_url': tree_node.get('image_url', merged_node.get('image_url', '')),
                    'parent_external_id': tree_node.get('parent_external_id'),
                    'column_index': tree_node.get('column_index'),
                    'row_index': tree_node.get('row_index'),
                    'order_in_folder': tree_node.get('order_in_folder'),
                    # Устанавливаем тип, если он есть в tree_node, иначе оставляем существующий или 'vehicle'
                    'type': tree_node.get('type', merged_node.get('type', 'vehicle')),
                     # Устанавливаем категорию, если она есть в tree_node, иначе оставляем существующую или 'standard'
                    'tech_category': tree_node.get('tech_category', merged_node.get('tech_category', 'standard'))
                })
            else:
                # Добавляем новую запись, если ее не было в list_view_data
                # Устанавливаем значения по умолчанию для новой записи
                tree_node.setdefault('type', 'vehicle')
                tree_node.setdefault('tech_category', 'standard')
                tree_node.setdefault('image_url', '') # Убедимся, что у новых записей есть image_url
                merged_dict[ext_id] = tree_node
                logging.info(f"Добавлен новый узел из tree_view_data с external_id='{ext_id}'.")

        # 3. Гарантируем наличие 'data_ulist_id'
        for key, item in merged_dict.items():
            if 'data_ulist_id' not in item or not item['data_ulist_id']:
                item['data_ulist_id'] = item.get('external_id', key) # Используем external_id или сам ключ словаря

        # 4. Преобразование в список
        merged_data = list(merged_dict.values())

        # 5. Обработка групповых узлов ('folder')
        folder_items = [item for item in merged_data if item.get('type') == 'folder']
        for idx, folder in enumerate(folder_items):
            # Установка виртуальных индексов для папок, если они отсутствуют
            if folder.get('row_index') is None:
                folder['row_index'] = 0 # Обычно папки вверху
            if folder.get('column_index') is None:
                folder['column_index'] = idx # Используем порядковый номер как индекс колонки
            if folder.get('order_in_folder') is None:
                 # Для папок order_in_folder может не иметь смысла или быть 0, если они не внутри другой папки
                 # Используем idx для уникальности, если необходимо
                 folder['order_in_folder'] = idx

        # Заполнение отсутствующих данных ('rank', 'country', 'vehicle_category') у папок
        for folder in folder_items:
            folder_id = folder.get('data_ulist_id')
            # Ищем дочерние ноды
            children = [n for n in merged_data if n.get('parent_external_id') == folder_id]

            if children:
                if not folder.get('rank'):
                    # Ищем подходящего ребенка для взятия ранга:
                    # Условие: order_in_folder существует (не None) и >= 0
                    valid_children_for_rank = [
                        child for child in children
                        if child.get('order_in_folder') is not None and isinstance(child.get('order_in_folder'), (int, float)) and child.get('order_in_folder') >= 0
                    ]
                    # Если нашли подходящих детей, берем ранг из первого такого ребенка
                    if valid_children_for_rank:
                        folder['rank'] = valid_children_for_rank[0].get('rank', '')
                        logging.debug(f"Для папки '{folder_id}' установлен ранг '{folder['rank']}' от ребенка '{valid_children_for_rank[0].get('data_ulist_id')}'.")
                    else:
                        # Если подходящих детей не найдено, можно либо оставить ранг пустым,
                        # либо взять от первого ребенка (как было раньше).
                        # Оставляем ранг пустым, согласно требованию "брался ранг ТОЛЬКО той ноды".
                        logging.debug(f"Для папки '{folder_id}' не найдено подходящих детей (с order_in_folder >= 0) для установки ранга.")
                        # Если нужен fallback: folder['rank'] = children[0].get('rank', '')

                # --- Логика для 'country' и 'vehicle_category' (остается прежней) ---
                if not folder.get('country'):
                    # Берем данные из первого ребенка в списке children
                    folder['country'] = children[0].get('country', '')
                    logging.debug(f"Для папки '{folder_id}' установлена страна '{folder['country']}' от первого ребенка '{children[0].get('data_ulist_id')}'.")

                if not folder.get('vehicle_category'):
                     # Берем данные из первого ребенка в списке children
                    folder['vehicle_category'] = children[0].get('vehicle_category', '')
                    logging.debug(f"Для папки '{folder_id}' установлена категория '{folder['vehicle_category']}' от первого ребенка '{children[0].get('data_ulist_id')}'.")
            else:
                logging.debug(f"Папка '{folder_id}' не имеет дочерних узлов в предоставленных данных.")


        logging.info(f"Слияние данных завершено. Итоговое количество узлов: {len(merged_data)}.")
        return merged_data

    def extract_node_dependencies(self, merged_data):
        """
        Извлекает зависимости между узлами на основе поля 'parent_external_id'.

        Проходит по объединенным данным и для каждого узла, имеющего 'parent_external_id',
        создает запись о зависимости вида {'node_external_id': ..., 'prerequisite_external_id': ...}.
        Пытается обработать случаи, когда родительский ID может иметь суффикс '_group'.

        :param merged_data: Список словарей с объединенными данными узлов (результат работы merge_data).
        :return: Список словарей, описывающих зависимости между узлами.
        :rtype: list[dict]
        """
        # Создаем словарь для быстрого поиска по 'data_ulist_id' для эффективности
        merged_dict = {item.get('data_ulist_id'): item for item in merged_data if item.get('data_ulist_id')}
        if not merged_dict:
             logging.warning("Не удалось создать словарь для поиска зависимостей, возможно, отсутствуют 'data_ulist_id'.")
             return []


        dependencies = []
        for item in merged_data:
            node_id = item.get('data_ulist_id')
            parent_ext_id = item.get('parent_external_id')

            if node_id and parent_ext_id:
                parent_found_id = None
                # Проверяем, существует ли родитель с таким ID напрямую
                if parent_ext_id in merged_dict:
                    parent_found_id = parent_ext_id
                else:
                    # Если родитель не найден, пробуем добавить суффикс "_group" (частый случай для папок)
                    alt_parent_id = parent_ext_id + "_group"
                    if alt_parent_id in merged_dict:
                        parent_found_id = alt_parent_id
                        logging.debug(f"Найден альтернативный родитель '{alt_parent_id}' для узла '{node_id}'.")

                # Если родитель найден (напрямую или с суффиксом)
                if parent_found_id:
                    dependencies.append({
                        'node_external_id': node_id,
                        'prerequisite_external_id': parent_found_id
                    })
                else:
                    logging.warning(f"Родительский узел с ID '{parent_ext_id}' (или '{parent_ext_id}_group') не найден для узла '{node_id}'. Зависимость не будет создана.")

        logging.info(f"Извлечено {len(dependencies)} зависимостей.")
        return dependencies

# Пример использования (если нужно протестировать)
if __name__ == '__main__':
    # Пример данных (замените на ваши реальные данные)
    list_data = [
        {'data_ulist_id': 'item1', 'name': 'Item 1', 'rank': 'A', 'country': 'USA'},
        {'data_ulist_id': 'item2', 'name': 'Item 2', 'rank': 'B', 'country': 'Canada'},
        {'data_ulist_id': 'item3', 'name': 'Item 3', 'rank': 'C', 'country': 'Mexico'},
        {'data_ulist_id': 'folder1', 'name': 'Folder 1'}, # Папка может не иметь ранга/страны в list view
        {'external_id': 'item_no_ulist', 'name': 'Item without ulist_id'} # Пример с external_id
    ]
    tree_data = [
        {'external_id': 'item1', 'parent_external_id': 'folder1', 'order_in_folder': 0, 'type': 'vehicle'},
        {'external_id': 'item2', 'parent_external_id': 'folder1', 'order_in_folder': None, 'type': 'vehicle'}, # order_in_folder = None
        {'external_id': 'item3', 'parent_external_id': 'folder1', 'order_in_folder': -1, 'type': 'vehicle'}, # order_in_folder < 0
        {'external_id': 'folder1', 'type': 'folder'},
        {'external_id': 'item_no_ulist', 'parent_external_id': 'folder1', 'order_in_folder': 1, 'type': 'vehicle', 'rank': 'D'} # Этот должен подойти для ранга
    ]

    # Создание экземпляра и вызов методов
    merger = NodesMerger(list_data, tree_data)
    merged_result = merger.merge_data()
    dependencies_result = merger.extract_node_dependencies(merged_result)

    # Вывод результатов (для демонстрации)
    import json
    print("--- Merged Data ---")
    print(json.dumps(merged_result, indent=2))

    print("\n--- Dependencies ---")
    print(json.dumps(dependencies_result, indent=2))

    # Проверка ранга папки folder1
    folder1_node = next((item for item in merged_result if item.get('data_ulist_id') == 'folder1'), None)
    if folder1_node:
        print(f"\nРанг папки 'folder1': {folder1_node.get('rank')}") # Должен быть 'A' от item1 или 'D' от item_no_ulist в зависимости от порядка
        # По коду item1 идет раньше, но order_in_folder = 0. item_no_ulist идет позже, но order_in_folder = 1.
        # Он возьмет ранг от первого подходящего, то есть от item1, ранг 'A'.
        # Если бы у item1 был order_in_folder = None или < 0, то он бы взял ранг 'D' от item_no_ulist
        print(f"Страна папки 'folder1': {folder1_node.get('country')}") # Должна быть 'USA' от item1 (первого ребенка)