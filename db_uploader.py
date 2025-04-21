# db_loader.py

import csv
from requests import HTTPError
from db_client import PostgrestClient

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

def upload_all_data(config,
                    target_sections,
                    country_csv="country_flags.csv",
                    merged_csv="vehicles_merged.csv",
                    deps_csv="dependencies.csv",
                    rank_csv="rank_requirements.csv"):
    """
    Полная заливка данных через PostgREST:
      1) Очистка (опционально)
      2) upsert vehicle_types
      3) upsert nations
      4) fetch_map для vehicle_types и nations
      5) build nodes_payload с корректной tech_category для папок
      6) по‑шаговая вставка nodes
      7) обновление parent_id
      8) insert node_dependencies
      9) insert rank_requirements
    """
    base_url = config.get('base_url')
    if not base_url:
        raise ValueError("В config.txt не указан base_url для PostgREST")
    client = PostgrestClient(base_url)

    # 1) очистка всех таблиц
    for tbl in ('node_dependencies','rank_requirements','nodes','nations','vehicle_types'):
        client.delete_all(tbl)

    # 2) vehicle_types
    print("Заливаю vehicle_types…")
    client.upsert_vehicle_types(target_sections)

    # 3) nations
    print("Заливаю nations…")
    nations_payload = []
    with open(country_csv, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            nations_payload.append({
                'name':      row['country'].strip().lower(),
                'image_url': row['flag_image_url'].strip()
            })
    client.upsert_nations(nations_payload)

    # 4) fetch_map справочников
    vt_map  = client.fetch_map('vehicle_types', key_field='name')
    nat_map = client.fetch_map('nations',       key_field='name')

    # 5) читаем merged CSV и строим payload для nodes
    merged_data = list(csv.DictReader(open(merged_csv, encoding='utf-8')))
    nodes_payload = []
    for nd in merged_data:
        ext = (nd.get('data_ulist_id') or '').strip()
        if not ext:
            print(f"[SKIP] нет external_id: {nd}")
            continue

        country_key = (nd.get('country') or '').strip().lower()
        if country_key not in nat_map:
            print(f"[SKIP] узел {ext}: неизвестная страна '{country_key}'")
            continue

        vt_key = (nd.get('vehicle_category') or '').strip()
        if vt_key not in vt_map:
            print(f"[SKIP] узел {ext}: неизвестный vehicle_type '{vt_key}'")
            continue

        # rank → int (араб./римские)
        r = (nd.get('rank') or '').strip()
        try:
            rank_int = int(r)
        except ValueError:
            rank_int = roman_to_int(r)

        # --- Новая логика для folder-узлов: ---
        if nd.get('type') == 'folder':
            tech_category = 'standard'
            silver_cost   = 0
            required_exp  = 0
        else:
            # silver_cost и required_exp для обычных юнитов
            silver_raw   = nd.get('silver') or None
            exp_raw      = nd.get('required_exp') or None
            silver_cost  = int(silver_raw) if silver_raw is not None else None
            required_exp = int(exp_raw)    if exp_raw    is not None else None

            # tech_category logic
            if silver_cost is not None:
                tech_category = 'standard'
                if required_exp is None:
                    required_exp = 0
            else:
                tech_category = 'premium'
                required_exp = None

        # парсим battle_rating
        br_raw = nd.get('battle_rating') or None
        if br_raw:
            try:
                br = float(br_raw.replace(',', '.'))
            except ValueError:
                br = None
        else:
            br = None

        nodes_payload.append({
            'external_id':     ext,
            'name':            nd.get('name') or ext,
            'type':            nd.get('type'),
            'tech_category':   tech_category,
            'nation_id':       nat_map[country_key],
            'vehicle_type_id': vt_map[vt_key],
            'rank':            rank_int,
            'silver_cost':     silver_cost,
            'required_exp':    required_exp,
            'image_url':       nd.get('image_url') or None,
            'br':              br,
            'column_index':    nd.get('column_index') or None,
            'row_index':       nd.get('row_index') or None,
            'order_in_folder': nd.get('order_in_folder') or None,
        })

    # 6) вставляем nodes по одной записи (для отладки)
    print("\n=== Вставка nodes по одной записи ===")
    for idx, rec in enumerate(nodes_payload, 1):
        try:
            client.insert_nodes([rec])
            print(f"[ OK ] #{idx}/{len(nodes_payload)} ext={rec['external_id']}")
        except HTTPError as e:
            print(f"[FAIL] #{idx}/{len(nodes_payload)} ext={rec['external_id']}")
            print(" status:", e.response.status_code)
            print(" body:", e.response.text)
            print(" payload:", rec)
            raise

    # 7) обновление parent_id
    print("\n=== Обновление parent_id ===")
    node_map = client.fetch_map('nodes', key_field='external_id')
    for nd in merged_data:
        ext    = (nd.get('data_ulist_id') or '').strip()
        parent = (nd.get('parent_external_id') or '').strip()
        print(f"обновляю {ext}, parent_id - {parent}")
        if ext in node_map and parent in node_map:
            client._patch(f"nodes?external_id=eq.{ext}",
                          {'parent_id': node_map[parent]})
    print("parent_id обновлены")

    # 8) node_dependencies
    print("\n=== Загрузка node_dependencies ===")
    deps = []
    with open(deps_csv, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            deps.append({
                'node_id':              node_map[row['node_external_id']],
                'prerequisite_node_id': node_map[row['prerequisite_external_id']]
            })
    client.insert_node_dependencies(deps)
    print(f"node dependecies : {deps}")

    # 9) rank_requirements
    print("\n=== Загрузка rank_requirements ===")
    rr = []
    with open(rank_csv, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            rr.append({
                'nation_id':        nat_map[row['nation'].strip().lower()],
                'vehicle_type_id':  vt_map[row['vehicle_type']],
                'target_rank':      int(row['target_rank']),
                'previous_rank':    int(row['previous_rank']),
                'required_units':   int(row['required_units']),
            })
    client.insert_rank_requirements(rr)
    print(f" rank_requirements : {rr}")

    print("\n✔ Всё успешно загружено через PostgREST")
