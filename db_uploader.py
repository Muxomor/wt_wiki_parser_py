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
    Полная заливка данных через PostgREST с аутентификацией парсера
    """
    base_url = config.get('base_url')
    api_key = config.get('parser_api_key')
    jwt_secret = config.get('jwt_secret')  # Новый параметр
    
    if not base_url:
        raise ValueError("В config.txt не указан base_url для PostgREST")
    
    if not api_key:
        print("⚠️  ВНИМАНИЕ: parser_api_key не указан в config.txt")
    
    if not jwt_secret:
        print("⚠️  ВНИМАНИЕ: jwt_secret не указан в config.txt")
    
    # Создаем клиент с JWT токеном
    client = PostgrestClient(base_url, api_key, jwt_secret)
    
    # Тестируем подключение
    print("🔍 Тестирование подключения...")
    client.test_connection()
    
    print("\n🚀 Начинаем загрузку данных...")

    # 1) очистка всех таблиц
    print("\n🗑️  Очистка таблиц...")
    for tbl in ('node_dependencies','rank_requirements','nodes','nations','vehicle_types'):
        try:
            client.delete_all(tbl)
        except Exception as e:
            print(f"❌ Ошибка очистки таблицы {tbl}: {e}")
            raise

    # 2) vehicle_types
    print("\n📝 Заливаю vehicle_types…")
    client.upsert_vehicle_types(target_sections)

    # 3) nations
    print("\n🏳️  Заливаю nations…")
    nations_payload = []
    try:
        with open(country_csv, encoding='utf-8') as f:
            for row in csv.DictReader(f):
                nations_payload.append({
                    'name':      row['country'].strip().lower(),
                    'image_url': row['flag_image_url'].strip()
                })
        client.upsert_nations(nations_payload)
    except FileNotFoundError:
        print(f"❌ Файл {country_csv} не найден")
        raise

    # 4) fetch_map справочников
    print("\n📋 Загружаю справочники...")
    vt_map  = client.fetch_map('vehicle_types', key_field='name')
    nat_map = client.fetch_map('nations',       key_field='name')

    # 5) читаем merged CSV и строим payload для nodes
    print(f"\n🚗 Читаю данные из {merged_csv}...")
    try:
        merged_data = list(csv.DictReader(open(merged_csv, encoding='utf-8')))
        print(f"📊 Найдено {len(merged_data)} записей для обработки")
    except FileNotFoundError:
        print(f"❌ Файл {merged_csv} не найден")
        raise
    
    nodes_payload = []
    overridden_by_strict_rules_count = 0

    for nd in merged_data:
        ext = (nd.get('data_ulist_id') or '').strip()
        if not ext:
            print(f"⚠️  нет external_id: {nd}")
            continue

        country_key = (nd.get('country') or '').strip().lower()
        if country_key not in nat_map:
            print(f"⚠️  узел {ext}: неизвестная страна '{country_key}'")
            continue

        vt_key = (nd.get('vehicle_category') or '').strip()
        if vt_key not in vt_map:
            print(f"⚠️  узел {ext}: неизвестный vehicle_type '{vt_key}'")
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

    if override_rules_data and overridden_by_strict_rules_count > 0:
        print(f"📝 Строгие правила применены к {overridden_by_strict_rules_count} узлам")

    # 6) вставляем nodes по одной записи
    print(f"\n🚗 Вставка {len(nodes_payload)} узлов...")
    for idx, rec in enumerate(nodes_payload, 1):
        try:
            client.insert_nodes([rec])
            if idx % 100 == 0:  # Прогресс каждые 100 записей
                print(f"📊 {idx}/{len(nodes_payload)} записей обработано")
        except HTTPError as e:
            print(f"❌ Ошибка вставки узла {rec['external_id']}:")
            print(f"   Статус: {e.response.status_code}")
            print(f"   Ответ: {e.response.text}")
            raise

    # 7) обновление parent_id
    print("\n🔗 Обновление parent_id...")
    node_map = client.fetch_map('nodes', key_field='external_id')
    updated_count = 0
    
    for nd in merged_data:
        ext_id_node  = (nd.get('data_ulist_id') or '').strip()
        parent_ext_id = (nd.get('parent_external_id') or '').strip()
        
        if ext_id_node in node_map and parent_ext_id and parent_ext_id in node_map:
            try:
                client._patch(f"nodes?external_id=eq.{ext_id_node}",
                              {'parent_id': node_map[parent_ext_id]})
                updated_count += 1
            except Exception as e_patch:
                print(f"⚠️  Ошибка обновления parent_id для {ext_id_node}: {e_patch}")
    
    print(f"✅ Обновлено {updated_count} связей parent_id")

    # 8) node_dependencies
    print(f"\n🔗 Загрузка зависимостей из {deps_csv}...")
    deps = []
    node_map_for_deps = client.fetch_map('nodes', key_field='external_id')
    
    try:
        with open(deps_csv, encoding='utf-8') as f:
            for row in csv.DictReader(f):
                node_id_val = row.get('node_external_id')
                prerequisite_id_val = row.get('prerequisite_external_id')

                if node_id_val in node_map_for_deps and prerequisite_id_val in node_map_for_deps:
                    deps.append({
                        'node_id':              node_map_for_deps[node_id_val],
                        'prerequisite_node_id': node_map_for_deps[prerequisite_id_val]
                    })
        
        if deps:
            client.insert_node_dependencies(deps)
        else:
            print("⚠️  Зависимости не найдены")
            
    except FileNotFoundError:
        print(f"⚠️  Файл {deps_csv} не найден, пропуск зависимостей")

    # 9) rank_requirements
    print(f"\n🎖️  Загрузка требований по рангам из {rank_csv}...")
    rr = []
    
    try:
        with open(rank_csv, encoding='utf-8') as f:
            for row in csv.DictReader(f):
                nation_name_key = row.get('nation','').strip().lower()
                vehicle_type_name_key = row.get('vehicle_type','')
                
                if nation_name_key not in nat_map:
                    continue
                if vehicle_type_name_key not in vt_map:
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
        else:
            print("⚠️  Требования по рангам не найдены")
            
    except FileNotFoundError:
        print(f"⚠️  Файл {rank_csv} не найден, пропуск требований по рангам")

    print("\n🎉 Всё успешно загружено через PostgREST!")