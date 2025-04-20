# db_loader.py

import csv
from db_client import PostgrestClient

def upload_all_data(config,
                    target_sections,
                    country_csv="country_flags.csv",
                    merged_csv="vehicles_merged.csv",
                    deps_csv="dependencies.csv",
                    rank_csv="rank_requirements.csv"):

    base_url = config.get('base_url')
    if not base_url:
        raise ValueError("В config.txt не указан base_url для PostgREST")

    client = PostgrestClient(base_url)

    for tbl in (
        'node_dependencies',
        'rank_requirements',
        'nodes',
        'nations',
        'vehicle_types'
    ):
        client.delete_all(tbl)
        print(f"  Таблица {tbl} очищена")

    # 1) vehicle_types
    client.upsert_vehicle_types(target_sections)

    # 2) nations
    nations_payload = []
    with open(country_csv, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            nations_payload.append({
                'name':      row['country'],
                'image_url': row['flag_image_url']
            })
    client.upsert_nations(nations_payload)

    # 3) получаем id‑маппинги
    vt_map  = client.fetch_map('vehicle_types',   key_field='name')
    nat_map = client.fetch_map('nations',         key_field='name')

    # Читаем merged CSV
    with open(merged_csv, encoding='utf-8') as f:
        merged_data = list(csv.DictReader(f))

    # Формируем список узлов без tech_category и с преобразованным rank
    nodes_payload = []
    for nd in merged_data:
        # Пропустим записи без rank
        rank_str = nd.get('rank') or ''
        try:
            rank_int = int(rank_str)
        except ValueError:
            # предполагаем римские цифры, например 'II', 'IV'
            rank_int = roman_to_int(rank_str)

        country_raw = nd.get('country', '').strip()
        country_key = country_raw.lower()  # если в nat_map ключи в lowercase
        if not country_key:
            print(f"Пропускаю узел {nd['external_id']}: не указана страна")
            continue
        if country_key not in nat_map:
            print(f"Пропускаю узел {nd['external_id']}: страна '{country_raw}' не найдена в nat_map")
            continue

           # аналогично можно нормализовать vehicle_category, убедиться, что есть в vt_map
        vt_raw = nd.get('vehicle_category', '').strip()
        vt_key = vt_raw  # или .lower() по аналогии
        if not vt_key or vt_key not in vt_map:
            print(f"Пропускаю узел {nd['external_id']}: vehicle_type '{vt_raw}' не найдена в vt_map")
            continue


        nodes_payload.append({
            'external_id':     nd['data_ulist_id'],
            'name':            nd['name'],
            'type':            nd['type'],
            'nation_id':       nat_map[nd['country']],
            'vehicle_type_id': vt_map[nd['vehicle_category']],
            'rank':            rank_int,
            'silver_cost':     nd.get('silver') or None,
            'required_exp':    nd.get('required_exp') or None,
            'image_url':       nd.get('image_url') or None,
            'column_index':    nd.get('column_index') or None,
            'row_index':       nd.get('row_index') or None,
            'order_in_folder': nd.get('order_in_folder') or None,
            # tech_category убрали — база подставит 'standard' по умолчанию
        })

    client.insert_nodes(nodes_payload)

    # 6) получаем mapping external_id → id
    node_map = client.fetch_map('nodes', key_field='external_id')

    # 7) обновляем parent_id через PATCH
    for nd in merged_data:
        parent = nd.get('parent_external_id')
        if parent:
            client._patch(
                f"nodes?external_id=eq.{nd['external_id']}",
                {'parent_id': node_map[parent]}
            )

    # 8) node_dependencies
    deps_payload = []
    with open(deps_csv, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            deps_payload.append({
                'node_id':               node_map[row['node_external_id']],
                'prerequisite_node_id':  node_map[row['prerequisite_external_id']]
            })
    client.insert_node_dependencies(deps_payload)

    # 9) rank_requirements
    rank_payload = []
    with open(rank_csv, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            rank_payload.append({
                'nation_id':        nat_map[row['nation']],
                'vehicle_type_id':  vt_map[row['vehicle_type']],
                'target_rank':      int(row['target_rank']),
                'previous_rank':    int(row['previous_rank']),
                'required_units':   int(row['required_units']),
            })
    client.insert_rank_requirements(rank_payload)

    print("✔ Все данные успешно загружены через PostgREST")

def roman_to_int(s: str) -> int:
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
