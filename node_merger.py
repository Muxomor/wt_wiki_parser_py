class NodesMerger:
    def __init__(self, list_view_data, tree_view_data):
        """
        :param list_view_data: список словарей из List View (обычно содержит ключ 'data_ulist_id')
        :param tree_view_data: список словарей из Tree View (с ключом 'external_id' и дополнительными полями,
                                 такими как 'parent_external_id', 'column_index', 'row_index', 'order_in_folder', 'image_url', 'type', 'tech_category')
        """
        self.list_view_data = list_view_data
        self.tree_view_data = tree_view_data

    def merge_data(self):
        merged_dict = {}
        for item in self.list_view_data:
            key = item.get('data_ulist_id') or item.get('external_id')
            if key:
                merged_dict[key] = item

        for tree_node in self.tree_view_data:
            ext_id = tree_node.get('external_id')
            if not ext_id:
                continue
            if ext_id in merged_dict:
                merged_dict[ext_id].update({
                    'image_url': tree_node.get('image_url', merged_dict[ext_id].get('image_url', '')),
                    'parent_external_id': tree_node.get('parent_external_id'),
                    'column_index': tree_node.get('column_index'),
                    'row_index': tree_node.get('row_index'),
                    'order_in_folder': tree_node.get('order_in_folder'),
                    'type': tree_node.get('type', merged_dict[ext_id].get('type', 'vehicle')),
                    'tech_category': tree_node.get('tech_category', merged_dict[ext_id].get('tech_category', 'standard'))
                })
            else:
                merged_dict[ext_id] = tree_node

        # Гарантируем, что каждый узел имеет ключ 'data_ulist_id'
        for item in merged_dict.values():
            if 'data_ulist_id' not in item or not item['data_ulist_id']:
                item['data_ulist_id'] = item.get('external_id', '')

        merged_data = list(merged_dict.values())

        # Для узлов типа folder, если индексы не вычислены, задаём виртуальные значения
        folder_items = [item for item in merged_data if item.get('type') == 'folder']
        for idx, folder in enumerate(folder_items):
            if folder.get('row_index') is None:
                folder['row_index'] = 0
            if folder.get('column_index') is None:
                folder['column_index'] = idx  # присваиваем порядковый номер как column_index
            if folder.get('order_in_folder') is None:
                folder['order_in_folder'] = idx

        return merged_data

    def extract_node_dependencies(self, merged_data):
        # Создаем словарь для быстрого поиска по 'data_ulist_id'
        merged_dict = {}
        for item in merged_data:
            key = item.get('data_ulist_id')
            if key:
                merged_dict[key] = item

        dependencies = []
        for item in merged_data:
            key = item.get('data_ulist_id')
            parent_ext = item.get('parent_external_id')
            if parent_ext:
                # Если родитель не найден, пробуем добавить суффикс "_group"
                if parent_ext not in merged_dict:
                    alt = parent_ext + "_group"
                    if alt in merged_dict:
                        parent_ext = alt
                if parent_ext in merged_dict:
                    dependencies.append({
                        'node_external_id': key,
                        'prerequisite_external_id': parent_ext
                    })
        return dependencies
