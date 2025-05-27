import requests

class PostgrestClient:
    def __init__(self, base_url):
        self.base = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update({
            'Content-Type': 'application/json'
        })

    def delete_all(self, table):
        url = f"{self.base}/{table}"
        r = self.session.delete(url)
        r.raise_for_status()
        return r.status_code

    def _post(self, path, data):
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
        url = f"{self.base}/{path}"
        r = self.session.get(url, params=params)
        r.raise_for_status()
        return r.json()

    def _patch(self, path, data):
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
        return self._post('vehicle_types', [{'name': n} for n in names])

    def upsert_nations(self, nations):
        return self._post('nations', nations)

    def fetch_map(self, table, key_field='name'):
        data = self._get(table, params={'select': f"id,{key_field}"})
        return {rec[key_field]: rec['id'] for rec in data}

    def insert_nodes(self, nodes_payload):
        return self._post('nodes', nodes_payload)

    def insert_node_dependencies(self, deps_payload):
        return self._post('node_dependencies', deps_payload)

    def insert_rank_requirements(self, reqs_payload):
        return self._post('rank_requirements', reqs_payload)
