class NodesMerger:
    def __init__(self, list_view_data, tree_view_data):
        """
        :param list_view_data: список словарей, полученных из List View (например, результат вызова parse_vehicle_row и VehicleDataFetcher)
                                Каждый словарь должен содержать ключ 'data_ulist_id'
        :param tree_view_data: список словарей, полученных из Tree View (например, результат работы TreeDataExtractor)
                                Каждый словарь должен содержать ключ 'external_id' и дополнительные поля:
                                'parent_external_id', 'column_index', 'row_index', 'order_in_folder', 'image_url'
        """
        self.list_view_data = list_view_data
        self.tree_view_data = tree_view_data

    def merge_data(self):
        """
        Объединяет данные из list_view_data и tree_view_data по совпадению внешнего идентификатора.
        Ключ сопоставления:
            list_view_data['data_ulist_id'] == tree_view_data['external_id']
        Если найдено соответствие, обновляет запись из list_view_data ключами:
            - image_url
            - parent_external_id
            - column_index
            - row_index
            - order_in_folder
        Возвращает новый список объединённых данных.
        """
        # Создаем словарь для быстрого поиска: key = external_id из tree_view_data
        tree_dict = {node['external_id']: node for node in self.tree_view_data if node.get('external_id')}
        merged = []
        for item in self.list_view_data:
            key = item.get('data_ulist_id')
            if key and key in tree_dict:
                tree_node = tree_dict[key]
                item.update({
                    'image_url': tree_node.get('image_url', item.get('image_url', '')),
                    'parent_external_id': tree_node.get('parent_external_id'),
                    'column_index': tree_node.get('column_index'),
                    'row_index': tree_node.get('row_index'),
                    'order_in_folder': tree_node.get('order_in_folder')
                })
            merged.append(item)
        return merged

    def extract_node_dependencies(self, merged_data):
        """
        Формирует список зависимостей для таблицы node_dependencies.
        Для каждого узла, у которого задано поле parent_external_id,
        если родитель найден среди объединённых данных, формируется зависимость.
        
        Возвращает список словарей вида:
            [{'node_external_id': <child_id>, 'prerequisite_external_id': <parent_id>}, ...]
        Здесь под внешним идентификатором подразумевается значение ключа 'data_ulist_id'.
        """
        # Создаем словарь для быстрого поиска по external_id (из merged_data)
        merged_dict = {item['data_ulist_id']: item for item in merged_data if item.get('data_ulist_id')}
        dependencies = []
        for item in merged_data:
            parent_ext = item.get('parent_external_id')
            if parent_ext and parent_ext in merged_dict:
                dependencies.append({
                    'node_external_id': item['data_ulist_id'],
                    'prerequisite_external_id': parent_ext
                })
        return dependencies
