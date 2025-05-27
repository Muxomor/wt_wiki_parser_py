import csv
from requests import HTTPError
from data_utils import roman_to_int
from db_client import PostgrestClient 

def upload_all_data(config,
                      target_sections,
                      override_rules_data=None,
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
    
    overridden_by_strict_rules_count = 0

    for nd in merged_data:
        ext = (nd.get('data_ulist_id') or '').strip()
        if not ext:
            print(f"нет external_id: {nd}")
            continue

        country_key = (nd.get('country') or '').strip().lower()
        if country_key not in nat_map:
            print(f"узел {ext}: неизвестная страна '{country_key}'")
            continue

        vt_key = (nd.get('vehicle_category') or '').strip()
        if vt_key not in vt_map:
            print(f"узел {ext}: неизвестный vehicle_type '{vt_key}'")
            continue

        r = (nd.get('rank') or '').strip()
        try:
            rank_int = int(r)
        except ValueError:
            rank_int = roman_to_int(r)

        if nd.get('type') == 'folder':
            tech_category = nd.get('tech_category') 
            silver_cost   = 0
            required_exp  = 0
        else:
            silver_raw   = nd.get('silver') or None
            exp_raw      = nd.get('required_exp') or None
            silver_cost  = int(silver_raw) if silver_raw is not None and silver_raw != '' else None
            required_exp = int(exp_raw)    if exp_raw is not None and exp_raw != '' else None
            
            if silver_cost is not None:
                tech_category = 'standard'
                if required_exp is None:
                    required_exp = 0
            else:
                tech_category = 'premium'
                required_exp = None

        if override_rules_data:
            node_id_for_rules_1 = ext 
            node_id_for_rules_2 = nd.get('external_id', '').strip()

            forced_category_from_rule = None
            
            if node_id_for_rules_1 and node_id_for_rules_1 in override_rules_data:
                forced_category_from_rule = override_rules_data[node_id_for_rules_1]
            elif node_id_for_rules_2 and node_id_for_rules_2 in override_rules_data: 
                forced_category_from_rule = override_rules_data[node_id_for_rules_2]
            
            if forced_category_from_rule:
                if tech_category != forced_category_from_rule:
                    # print(f"Узел '{ext}': tech_category '{tech_category}' изменен на '{forced_category_from_rule}' строгим правилом.")
                    overridden_by_strict_rules_count += 1
                tech_category = forced_category_from_rule 

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

    if override_rules_data:
        if overridden_by_strict_rules_count > 0:
            print(f"Строгие правила tech_category были применены к {overridden_by_strict_rules_count} узлам.")
        else:
            print("Не было узлов, для которых требовалось бы изменение tech_category согласно строгим правилам, или их категории уже совпали.")

    # 6) вставляем nodes по одной записи (для отладки)
    print("\nВставка nodes по одной записи")
    for idx, rec in enumerate(nodes_payload, 1):
        try:
            client.insert_nodes([rec])
            print(f"{idx}/{len(nodes_payload)} ext={rec['external_id']}")
        except HTTPError as e:
            print(f"{idx}/{len(nodes_payload)} ext={rec['external_id']}")
            print("status:", e.response.status_code)
            print("body:", e.response.text)
            print("payload:", rec)
            raise

    # 7) обновление parent_id
    print("\nОбновление parent_id")
    node_map = client.fetch_map('nodes', key_field='external_id')
    for nd in merged_data:
        ext_id_node  = (nd.get('data_ulist_id') or '').strip()
        parent_ext_id = (nd.get('parent_external_id') or '').strip()
        
        print(f"обновляю {ext_id_node}, parent_external_id - {parent_ext_id}")
        if ext_id_node in node_map and parent_ext_id and parent_ext_id in node_map:
            try:
                client._patch(f"nodes?external_id=eq.{ext_id_node}",
                              {'parent_id': node_map[parent_ext_id]})
            except Exception as e_patch:
                print(f"[WARN] Ошибка обновления parent_id для {ext_id_node} (родитель {parent_ext_id}): {e_patch}")
        # elif parent_ext_id: # Если parent_ext_id есть, но не найден в node_map
            # print(f"Родительский узел с external_id '{parent_ext_id}' не найден в БД для узла '{ext_id_node}'.")

    print("parent_id обновлены")

    # 8) node_dependencies
    print("\nЗагрузка node_dependencies")
    deps = []
    node_map_for_deps = client.fetch_map('nodes', key_field='external_id')
    with open(deps_csv, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            node_id_val = row.get('node_external_id')
            prerequisite_id_val = row.get('prerequisite_external_id')

            if node_id_val in node_map_for_deps and prerequisite_id_val in node_map_for_deps:
                deps.append({
                    'node_id':              node_map_for_deps[node_id_val],
                    'prerequisite_node_id': node_map_for_deps[prerequisite_id_val]
                })
            # else:
                # print(f"Пропуск зависимости: один из ID не найден в node_map. Узел: {node_id_val}, Пререквизит: {prerequisite_id_val}")
    if deps:
        client.insert_node_dependencies(deps)
    # print(f"node dependecies : {deps}") # Может быть очень длинным
    print(f"Загружено {len(deps)} зависимостей.")


    # 9) rank_requirements
    print("\nЗагрузка rank_requirements")
    rr = []
    with open(rank_csv, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            nation_name_key = row.get('nation','').strip().lower()
            vehicle_type_name_key = row.get('vehicle_type','')
            
            if nation_name_key not in nat_map:
                # print(f"Пропуск rank_requirement: нация '{nation_name_key}' не найдена.")
                continue
            if vehicle_type_name_key not in vt_map:
                # print(f"Пропуск rank_requirement: тип техники '{vehicle_type_name_key}' не найден.")
                continue
                
            rr.append({
                'nation_id':       nat_map[nation_name_key],
                'vehicle_type_id': vt_map[vehicle_type_name_key],
                'target_rank':     int(row['target_rank']),
                'previous_rank':   int(row['previous_rank']),
                'required_units':  int(row['required_units']),
            })
    if rr:
        client.insert_rank_requirements(rr)
    # print(f"rank_requirements : {rr}")
    print(f"Загружено {len(rr)} требований по рангам.")


    print("\nВсё успешно загружено через PostgREST")