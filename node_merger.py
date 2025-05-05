import pprint 

class NodesMerger:
    """
    Объединяет данные узлов из List View и Tree View.
    """
    def __init__(self, list_view_data, tree_view_data):
        """
        Инициализирует NodesMerger.
        """
        self.list_view_data = list_view_data if list_view_data is not None else []
        self.tree_view_data = tree_view_data if tree_view_data is not None else []
        print(f"Инициализация NodesMerger с {len(self.list_view_data)} элементами List View и {len(self.tree_view_data)} элементами Tree View.")

    def _get_definitive_id(self, node):
         """Возвращает приоритетный ID узла (data_ulist_id или external_id)."""
         return node.get('data_ulist_id') or node.get('external_id')

    def merge_data(self):
        """
        Выполняет слияние данных list_view_data и tree_view_data.
        """
        merged_dict_by_id = {} 

        # 1. Заполнение из List View
        processed_list_view_count = 0
        skipped_list_view_no_id = 0
        for item in self.list_view_data:
            key = self._get_definitive_id(item)
            if key:
                # Добавляем недостающие поля из tree view как None по умолчанию
                item.setdefault('image_url', None)
                item.setdefault('parent_external_id', None)
                item.setdefault('column_index', None)
                item.setdefault('row_index', None)
                item.setdefault('order_in_folder', None)
                item.setdefault('type', 'vehicle') 
                item.setdefault('tech_category', 'standard')
                merged_dict_by_id[key] = item
                processed_list_view_count += 1
            else:
                skipped_list_view_no_id += 1
        print(f"Обработано из List View: {processed_list_view_count} (пропущено без ID: {skipped_list_view_no_id})")


        # 2. Объединение с данными из Tree View
        updated_count = 0
        added_count = 0
        skipped_tree_view_no_id = 0
        for tree_node in self.tree_view_data:
            key = self._get_definitive_id(tree_node)
            if not key:
                skipped_tree_view_no_id += 1
                continue

            if key in merged_dict_by_id:
                merged_node = merged_dict_by_id[key]
                merged_node['image_url'] = tree_node.get('image_url', merged_node.get('image_url')) # Оставляем старое, если в tree нет
                merged_node['parent_external_id'] = tree_node.get('parent_external_id', merged_node.get('parent_external_id'))
                merged_node['column_index'] = tree_node.get('column_index', merged_node.get('column_index'))
                merged_node['row_index'] = tree_node.get('row_index', merged_node.get('row_index'))
                merged_node['order_in_folder'] = tree_node.get('order_in_folder', merged_node.get('order_in_folder'))
                merged_node['type'] = tree_node.get('type', merged_node.get('type', 'vehicle'))
                merged_node['tech_category'] = tree_node.get('tech_category', merged_node.get('tech_category', 'standard'))
                if tree_node.get('name') and tree_node.get('name') != merged_node.get('name'):
                     pass 
                updated_count += 1
            else:
                tree_node.setdefault('link', '')
                tree_node.setdefault('country', '')
                tree_node.setdefault('battle_rating', '')
                tree_node.setdefault('silver', None)
                tree_node.setdefault('rank', '')
                tree_node.setdefault('vehicle_category', '')
                tree_node.setdefault('required_exp', None)
                tree_node.setdefault('image_url', '')
                tree_node.setdefault('parent_external_id', '')
                tree_node.setdefault('column_index', None)
                tree_node.setdefault('row_index', None)
                tree_node.setdefault('order_in_folder', None) 
                tree_node.setdefault('type', 'vehicle')
                tree_node.setdefault('tech_category', 'standard')

                merged_dict_by_id[key] = tree_node
                added_count += 1
        print(f"Обновлено из Tree View: {updated_count}")
        print(f"Добавлено из Tree View: {added_count} (пропущено без ID: {skipped_tree_view_no_id})")

        # 3. Преобразование в список
        merged_data = list(merged_dict_by_id.values())
        print(f"Всего узлов перед обработкой папок: {len(merged_data)}")

        # 4. Пост-обработка: Заполнение данных для папок на основе детей
        folder_items = [item for item in merged_data if item.get('type') == 'folder']
        print(f"Найдено папок для пост-обработки: {len(folder_items)}")

        nodes_by_definitive_id = {self._get_definitive_id(n): n for n in merged_data if self._get_definitive_id(n)}

        processed_folders = 0
        for folder in folder_items:
            folder_id = self._get_definitive_id(folder)
            if not folder_id: continue

            # Ищем дочерние узлы (те, у кого parent_external_id равен ID папки)
            children = [
                n for n in merged_data
                if n.get('parent_external_id') == folder_id
            ]

            if children:
                # --- Заполнение 'rank' ---
                if not folder.get('rank'):
                    # Ищем первого подходящего ребенка для ранга
                    suitable_child_for_rank = None
                    children.sort(key=lambda x: x.get('order_in_folder') if x.get('order_in_folder') is not None else float('inf'))

                    for child in children:
                         child_order = child.get('order_in_folder')
                         is_suitable = (
                              child.get('type') == 'vehicle' and
                              child.get('rank') and
                              child_order is not None and
                              isinstance(child_order, (int, float)) and
                              child_order >= 0
                         )
                         if is_suitable:
                              suitable_child_for_rank = child
                              break

                    if suitable_child_for_rank:
                        folder['rank'] = suitable_child_for_rank.get('rank')


                # --- Заполнение 'country' и 'vehicle_category' (берем из первого ребенка) ---
                first_child = children[0]
                if not folder.get('country'):
                    folder['country'] = first_child.get('country', '')
                if not folder.get('vehicle_category'):
                    folder['vehicle_category'] = first_child.get('vehicle_category', '')


                processed_folders += 1

        print(f"Пост-обработка папок завершена (обработано {processed_folders}).")

        # 5. Финальная проверка (опционально) - Убедимся, что у всех узлов есть имя? Нет, имя может отсутствовать у техники из TreeView до слияния.
        final_count = len(merged_data)
        print(f"Слияние данных завершено. Итого узлов: {final_count}.")

        return merged_data


    def extract_node_dependencies(self, merged_data):
        """
        Извлекает зависимости между узлами на основе поля 'parent_external_id'.
        """
        if not merged_data:
            print("Нет данных для извлечения зависимостей.")
            return []

        nodes_by_definitive_id = {self._get_definitive_id(n): n for n in merged_data if self._get_definitive_id(n)}
        if not nodes_by_definitive_id:
             print("Предупреждение: Не удалось создать словарь узлов по ID для поиска зависимостей.")
             return []

        dependencies = []
        processed_nodes = 0
        dependencies_found = 0
        parent_not_found_count = 0

        for item in merged_data:
            processed_nodes += 1
            node_id = self._get_definitive_id(item)
            parent_ext_id = item.get('parent_external_id')

            if node_id and parent_ext_id:
                if parent_ext_id in nodes_by_definitive_id:
                    dependencies.append({
                        'node_external_id': node_id,
                        'prerequisite_external_id': parent_ext_id
                    })
                    dependencies_found += 1
                else:
                    alt_parent_id = parent_ext_id + "_group"
                    if alt_parent_id in nodes_by_definitive_id:
                         dependencies.append({
                            'node_external_id': node_id,
                            'prerequisite_external_id': alt_parent_id
                         })
                         dependencies_found += 1
                    else:
                        parent_not_found_count += 1

        print(f"Извлечение зависимостей завершено. Обработано узлов: {processed_nodes}. Найдено зависимостей: {dependencies_found} (родитель не найден: {parent_not_found_count}).")
        return dependencies
