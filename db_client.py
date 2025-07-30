import requests
import jwt
import time

class PostgrestClient:
    def __init__(self, base_url, api_key=None, jwt_secret=None):
        self.base = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.trust_env = False
        
        headers = {'Content-Type': 'application/json'}
        
        # Добавляем аутентификацию для парсера
        if api_key and jwt_secret:
            # Создаем JWT токен для парсера
            payload = {
                'role': 'parser_role',
                'aud': 'postgrest',
                'exp': int(time.time()) + 3600  # 1 час
            }
            token = jwt.encode(payload, jwt_secret, algorithm='HS256')
            headers['Authorization'] = f'Bearer {token}'
            print("✅ Парсер авторизован с JWT токеном")
        elif api_key:
            # Fallback на простой API ключ
            headers['Authorization'] = f'Bearer {api_key}'
            print("✅ Парсер авторизован с API ключом")
        else:
            print("⚠️  Работа без аутентификации (только чтение)")
            
        self.session.headers.update(headers)

    def delete_all(self, table):
        """Удаление всех записей из таблицы"""
        url = f"{self.base}/{table}"
        r = self.session.delete(url)
        r.raise_for_status()
        print(f"✅ Очищена таблица {table}")
        return r.status_code

    def _post(self, path, data):
        """POST запрос"""
        url = f"{self.base}/{path}"
        r = self.session.post(url, json=data)
        r.raise_for_status()
        if r.text:
            try:
                return r.json()
            except ValueError:
                return r.status_code
        return r.status_code

    def _get(self, path, params=None):
        """GET запрос"""
        url = f"{self.base}/{path}"
        r = self.session.get(url, params=params)
        r.raise_for_status()
        return r.json()

    def _patch(self, path, data):
        """PATCH запрос"""
        url = f"{self.base}/{path}"
        r = self.session.patch(url, json=data)
        r.raise_for_status()
        if r.text:
            try:
                return r.json()
            except ValueError:
                return r.status_code
        return r.status_code

    def upsert_vehicle_types(self, names):
        """Вставка типов техники"""
        payload = [{'name': n} for n in names]
        result = self._post('vehicle_types', payload)
        print(f"✅ Загружено {len(names)} типов техники")
        return result

    def upsert_nations(self, nations):
        """Вставка наций"""
        result = self._post('nations', nations)
        print(f"✅ Загружено {len(nations)} наций")
        return result

    def fetch_map(self, table, key_field='name'):
        """Получение справочника id -> name"""
        data = self._get(table, params={'select': f"id,{key_field}"})
        mapping = {rec[key_field]: rec['id'] for rec in data}
        print(f"✅ Загружен справочник {table}: {len(mapping)} записей")
        return mapping

    def insert_nodes(self, nodes_payload):
        """Вставка узлов техники"""
        return self._post('nodes', nodes_payload)

    def insert_node_dependencies(self, deps_payload):
        """Вставка зависимостей между узлами"""
        result = self._post('node_dependencies', deps_payload)
        print(f"✅ Загружено {len(deps_payload)} зависимостей")
        return result

    def insert_rank_requirements(self, reqs_payload):
        """Вставка требований по рангам"""
        result = self._post('rank_requirements', reqs_payload)
        print(f"✅ Загружено {len(reqs_payload)} требований по рангам")
        return result
    
    def test_connection(self):
        """Тест подключения и прав доступа"""
        try:
            # Тест чтения
            response = self._get("nodes", params={'limit': '1'})
            print("✅ Чтение работает")
            
            # Тест записи (создание и удаление тестовой записи)
            test_nation = {
                "name": "TEST_NATION_DELETE_ME",
                "image_url": "test.png"
            }
            
            try:
                self._post("nations", [test_nation])
                print("✅ Запись работает")
                # Удаляем тестовую запись
                self.session.delete(f"{self.base}/nations?name=eq.TEST_NATION_DELETE_ME")
            except Exception as e:
                print(f"❌ Ошибка записи: {e}")
                
        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")