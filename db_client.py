# db_client.py

import requests

class PostgrestClient:
    def __init__(self, base_url):
        """
        Создаёт сессию requests с trust_env=False,
        чтобы игнорировать переменные HTTP_PROXY/SOCKS_PROXY.
        """
        self.base = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.trust_env = False 
        self.session.headers.update({
            'Content-Type': 'application/json'
        })

    def delete_all(self, table):
        """
        Удалить все строки из таблицы table.
        DELETE /<table> без фильтрации = удаляет всё.
        """
        url = f"{self.base}/{table}"
        resp = self.session.delete(url)
        resp.raise_for_status()
        return resp.status_code

    def _post(self, path, data):
        """
        Делает POST и спокойно обрабатывает пустые ответы.
        """
        url = f"{self.base}/{path}"
        r = self.session.post(url, json=data)
        r.raise_for_status()
    
        # Если тело непустое — пытаемся его распарсить как JSON,
        # иначе — возвращаем просто статус-код или сам response.
        if r.text:
            try:
                return r.json()
            except ValueError:
                return r.status_code
        return r.status_code

    def _get(self, path, params=None):
        url = f"{self.base}/{path}"
        r = self.session.get(url, params=params)
        r.raise_for_status()
        return r.json()

    def _patch(self, path, data):
        url = f"{self.base}/{path}"

        r = self.session.patch(url, json=data)
        r.raise_for_status()
        return r.json()

    # -------- Справочники --------
    def upsert_vehicle_types(self, names):
        payload = [{'name': n} for n in names]
        return self._post('vehicle_types', payload)

    def upsert_nations(self, nations):
        # nations: list of {'name':..., 'image_url':...}
        return self._post('nations', nations)

    def fetch_map(self, table, key_field='name'):
        # GET /<table>?select=id,<key_field>
        data = self._get(table, params={'select': f"id,{key_field}"})
        return {rec[key_field]: rec['id'] for rec in data}

    # -------- Основные вставки --------
    def insert_nodes(self, nodes_payload):
        return self._post('nodes', nodes_payload)

    def insert_node_dependencies(self, deps_payload):
        return self._post('node_dependencies', deps_payload)

    def insert_rank_requirements(self, reqs_payload):
        return self._post('rank_requirements', reqs_payload)
