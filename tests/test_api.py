import base64
import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.config import Settings
from app.db.session import Database
from app.main import create_app
from app.manage import import_legacy
from app.db.models import Address, Base, Customer, FabricTier, Order, OrderItem, Payment, Product, Project
from app.core.security import hash_password, read_token
from app.db.seed import seed_catalog

LEGACY = json.loads((Path(__file__).parent / 'fixtures/node-auth.json').read_text())


class DatabaseCase(unittest.TestCase):
    """PostgreSQL real; cada prueba usa y elimina únicamente su esquema temporal."""

    def setUp(self):
        settings = Settings.from_env()
        self.url = os.getenv('TEST_DATABASE_URL', settings.database_url)
        self.schema = 'test_camisetalibre_' + uuid4().hex
        self.admin = create_engine(self.url, hide_parameters=True)
        with self.admin.begin() as connection:
            connection.execute(CreateSchema(self.schema))
        self.addCleanup(self.cleanup_schema)
        self.db = Database(self.url)
        self.db.engine = self.db.engine.execution_options(schema_translate_map={None: self.schema})
        self.db.sessions.configure(bind=self.db.engine)
        self.addCleanup(self.db.close)
        Base.metadata.create_all(self.db.engine)
        with self.db.sessions.begin() as session:
            seed_catalog(session)
        self.settings = Settings(secret=LEGACY['secret'], database_url=self.url)
        self.app = create_app(self.settings, database=self.db)
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)

    def cleanup_schema(self):
        with self.admin.begin() as connection:
            connection.execute(DropSchema(self.schema, cascade=True))
        self.admin.dispose()

    def count(self, model):
        with self.db.sessions() as session:
            return session.scalar(select(func.count()).select_from(model))

    def register(self, email='cliente@example.test'):
        return self.client.post('/api/auth/register', json={'name': ' Cliente Prueba ', 'email': email, 'password': LEGACY['password']})

    def headers(self, email='cliente@example.test'):
        result = self.register(email)
        self.assertEqual(result.status_code, 201, result.text)
        return {'Authorization': 'Bearer ' + result.json()['token']}

    def line(self, quantity=8, product='camiseta', fabric='eco', size='M', **extra):
        return {'productId': product, 'fabricId': fabric, 'sizeId': size, 'quantity': quantity, **extra}



class ApiTests(DatabaseCase):
    def test_registration_login_and_persistence(self):
        response = self.register(' CLIENTE@example.test ')
        self.assertEqual(response.status_code, 201)
        user = response.json()['user']
        self.assertEqual(user['name'], 'Cliente Prueba')
        self.assertEqual(user['email'], 'cliente@example.test')
        self.assertNotIn('passwordHash', user)
        login = self.client.post('/api/auth/login', json={'email': 'CLIENTE@example.test', 'password': LEGACY['password']})
        self.assertEqual(login.status_code, 200)
        with TestClient(create_app(self.settings, database=self.db)) as restarted:
            result = restarted.get('/api/auth/me', headers={'Authorization': 'Bearer ' + login.json()['token']})
            self.assertEqual(result.json(), {'user': user})
        with self.db.sessions() as session:
            stored = session.get(Customer, user['id'])
            self.assertNotEqual(stored.password_hash, LEGACY['password'])

    def test_duplicate_and_concurrent_registration(self):
        with ThreadPoolExecutor(max_workers=4) as executor:
            statuses = list(executor.map(lambda _: self.register().status_code, range(4)))
        self.assertEqual(sorted(statuses), [201, 409, 409, 409])
        self.assertEqual(self.count(Customer), 1)

    def test_invalid_registration_and_login(self):
        for fields in ({}, {'name': ' ', 'email': 'a@b.c', 'password': '12345678'},
                       {'name': 'Ana', 'email': 'invalid', 'password': '12345678'},
                       {'name': 'Ana', 'email': 'a@b.c', 'password': 12345678}):
            result = self.client.post('/api/auth/register', json=fields)
            self.assertEqual(result.status_code, 422)
            self.assertIn('error', result.json())
        self.headers()
        result = self.client.post('/api/auth/login', json={'email': 'cliente@example.test', 'password': 'incorrecta'})
        self.assertEqual(result.status_code, 401)
        self.assertEqual(result.json(), {'error': 'Email o contraseña incorrectos.'})

    def test_protected_routes(self):
        for method, path in (('GET', '/api/auth/me'), ('GET', '/api/projects'), ('POST', '/api/projects'),
                             ('GET', '/api/orders'), ('POST', '/api/orders'), ('GET', '/api/customers/me/addresses')):
            result = self.client.request(method, path, json={})
            self.assertEqual(result.status_code, 401, result.text)
        self.assertEqual(self.client.get('/api/auth/me', headers={'Authorization': 'Bearer invalid'}).status_code, 401)

    def test_node_accounts_and_tokens_import_idempotently(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'store.json'
            path.write_text(json.dumps({'users': [{'id': 'legacy-user', 'name': 'Anterior', 'email': 'anterior@example.test',
                'passwordHash': LEGACY['passwordHash'], 'createdAt': '2026-01-01T00:00:00.000Z'}], 'projects': [
                {'id': 'old-project', 'ownerId': 'legacy-user', 'name': 'Anterior', 'design': {'color': 'azul'},
                 'createdAt': '2026-01-01T00:00:00.000Z', 'updatedAt': '2026-01-01T00:00:00.000Z'}]}))
            with self.db.sessions.begin() as session:
                self.assertEqual(import_legacy(session, path), {'customers': 1, 'projects': 1})
            with self.db.sessions.begin() as session:
                self.assertEqual(import_legacy(session, path), {'customers': 0, 'projects': 0})
        headers = {'Authorization': 'Bearer ' + LEGACY['token']}
        self.assertEqual(self.client.get('/api/auth/me', headers=headers).status_code, 200)
        self.assertEqual(self.client.get('/api/projects', headers=headers).json()['projects'][0]['id'], 'old-project')
        self.assertEqual(self.client.post('/api/auth/login', json={'email': 'anterior@example.test', 'password': LEGACY['password']}).status_code, 200)
        self.assertEqual(hash_password(LEGACY['password'], '0123456789abcdef0123456789abcdef'), LEGACY['passwordHash'])

    def test_project_ownership_and_partial_updates(self):
        headers = self.headers()
        other = self.headers('otro@example.test')
        result = self.client.post('/api/projects', headers=headers, json={'name': 'Mi camiseta', 'productId': 'camiseta', 'design': {'layers': [1, 2]}})
        self.assertEqual(result.status_code, 201)
        path = '/api/projects/' + result.json()['project']['id']
        self.assertEqual(self.client.get('/api/projects', headers=other).json(), {'projects': []})
        self.assertEqual(self.client.put(path, headers=other, json={'name': 'Robado'}).status_code, 404)
        updated = self.client.put(path, headers=headers, json={'name': 'Actualizado'}).json()['project']
        self.assertEqual(updated['design'], {'layers': [1, 2]})
        self.assertEqual(updated['productId'], 'camiseta')
        self.assertEqual(self.client.post('/api/projects', headers=headers, json={'productId': 'missing'}).status_code, 422)

    def test_concurrent_project_writes(self):
        headers = self.headers()
        with ThreadPoolExecutor(max_workers=4) as executor:
            statuses = list(executor.map(lambda i: self.client.post('/api/projects', headers=headers, json={'name': str(i)}).status_code, range(12)))
        self.assertEqual(statuses, [201] * 12)
        self.assertEqual(self.count(Project), 12)

    def test_catalog_and_idempotent_seed(self):
        response = self.client.get('/api/catalog').json()
        self.assertEqual(response['currency'], 'ARS')
        prices = {p['id']: Decimal(p['basePrice']) for p in response['products']}
        self.assertEqual(prices, {'camiseta': 28000, 'chomba': 31000, 'musculosa': 20000, 'short': 18000})
        self.assertEqual([f['increasePercent'] for f in response['fabrics']], ['0.00', '20.00', '30.00'])
        with self.db.sessions.begin() as session:
            session.get(Product, 'short').base_price = Decimal('19000')
        with self.db.sessions.begin() as session:
            seed_catalog(session)
        with self.db.sessions() as session:
            self.assertEqual(session.get(Product, 'short').base_price, Decimal('19000'))
        self.assertEqual(self.count(Product), 4)

    def test_prices_for_every_product_and_fabric(self):
        for product, base in (('camiseta', 28000), ('chomba', 31000), ('musculosa', 20000), ('short', 18000)):
            for fabric, multiplier in (('eco', Decimal('1')), ('pro', Decimal('1.2')), ('premium', Decimal('1.3'))):
                with self.subTest(product=product, fabric=fabric):
                    response = self.client.post('/api/quotes', json={'items': [self.line(product=product, fabric=fabric)]})
                    self.assertEqual(response.status_code, 200, response.text)
                    item = response.json()['items'][0]
                    self.assertEqual(Decimal(item['unitPrice']), base * multiplier)
                    self.assertEqual(Decimal(response.json()['total']), base * multiplier * 8)

    def test_minimum_is_per_product_across_sizes(self):
        mixed_sizes = [self.line(4, size='M'), self.line(4, size='L')]
        self.assertEqual(self.client.post('/api/quotes', json={'items': mixed_sizes}).status_code, 200)
        mixed_products = [self.line(4), self.line(4, product='short')]
        self.assertEqual(self.client.post('/api/quotes', json={'items': mixed_products}).status_code, 422)
        for quantity in (0, -1, 7, 8.5, '8', True):
            self.assertEqual(self.client.post('/api/quotes', json={'items': [self.line(quantity)]}).status_code, 422)

    def test_client_cannot_supply_prices_or_invalid_catalog(self):
        headers = self.headers()
        for line in (self.line(unitPrice=1), self.line(product='missing'), self.line(fabric='missing'), self.line(size='missing')):
            self.assertEqual(self.client.post('/api/orders', headers=headers, json={'items': [line]}).status_code, 422)
        with self.db.sessions.begin() as session:
            session.get(Product, 'camiseta').active = False
        self.assertEqual(self.client.post('/api/orders', headers=headers, json={'items': [self.line()]}).status_code, 422)
        self.assertEqual(self.count(Order), 0)

    def test_profile_and_address_ownership(self):
        headers = self.headers()
        other = self.headers('otro@example.test')
        response = self.client.patch('/api/customers/me', headers=headers, json={'name': 'Ana Equipo', 'phone': '1133334444'})
        self.assertEqual(response.json()['user']['phone'], '1133334444')
        address = self.client.post('/api/customers/me/addresses', headers=headers, json={
            'recipient': 'Ana Equipo', 'phone': '1133334444', 'street': 'Calle 123', 'city': 'Buenos Aires',
            'province': 'Buenos Aires', 'postalCode': '1000'}).json()['address']
        self.assertEqual(self.client.get('/api/customers/me/addresses', headers=other).json(), {'addresses': []})
        self.assertEqual(self.client.post('/api/orders', headers=other, json={'items': [self.line()], 'addressId': address['id']}).status_code, 404)

    def test_order_snapshot_ownership_and_cancellation(self):
        headers = self.headers()
        other = self.headers('otro@example.test')
        project = self.client.post('/api/projects', headers=headers, json={'name': 'Diseño', 'productId': 'camiseta', 'design': {'color': 'verde'}}).json()['project']
        response = self.client.post('/api/orders', headers=headers, json={'items': [self.line(fabric='pro', projectId=project['id'])]})
        self.assertEqual(response.status_code, 201, response.text)
        order = response.json()['order']
        self.assertEqual(order['status'], 'pending')
        self.assertEqual(Decimal(order['total']), Decimal('268800'))
        path = '/api/orders/' + order['id']
        self.assertEqual(self.client.get(path, headers=other).status_code, 404)
        self.assertEqual(self.client.get('/api/orders', headers=other).json(), {'orders': []})
        with self.db.sessions.begin() as session:
            session.get(Product, 'camiseta').base_price = Decimal('99000')
            session.get(Project, project['id']).design = {'color': 'rojo'}
        old = self.client.get(path, headers=headers).json()['order']
        self.assertEqual(Decimal(old['total']), Decimal('268800'))
        self.assertEqual(old['items'][0]['design'], {'color': 'verde'})
        self.assertEqual(self.client.post(path + '/cancel', headers=other).status_code, 404)
        self.assertEqual(self.client.post(path + '/cancel', headers=headers).json()['order']['status'], 'cancelled')
        self.assertEqual(self.client.post(path + '/cancel', headers=headers).status_code, 409)
        self.assertEqual(self.count(Payment), 0)  # Crear pedidos no simula cobros.

    def test_cannot_order_another_customers_design(self):
        headers = self.headers()
        other = self.headers('otro@example.test')
        project = self.client.post('/api/projects', headers=headers, json={'productId': 'camiseta'}).json()['project']
        result = self.client.post('/api/orders', headers=other, json={'items': [self.line(projectId=project['id'])]})
        self.assertEqual(result.status_code, 404)
        self.assertEqual(self.count(Order), 0)
        self.assertEqual(self.count(OrderItem), 0)
        mismatch = self.client.post('/api/orders', headers=headers, json={'items': [self.line(product='short', projectId=project['id'])]})
        self.assertEqual(mismatch.status_code, 422)

    def test_database_constraints_and_rollback(self):
        headers = self.headers()
        response = self.client.post('/api/orders', headers=headers, json={'items': [self.line()]})
        order_id = response.json()['order']['id']
        with self.assertRaises(IntegrityError):
            with self.db.sessions.begin() as session:
                item = session.scalar(select(OrderItem).where(OrderItem.order_id == order_id))
                item.line_total = Decimal('1')
        with self.db.sessions() as session:
            self.assertEqual(session.get(Order, order_id).total, Decimal('224000'))
            self.assertEqual(session.scalar(select(OrderItem)).line_total, Decimal('224000'))
        with self.assertRaises(IntegrityError):
            with self.db.sessions.begin() as session:
                session.add(Project(owner_id='unknown', name='Orphan', design={}))

    def test_cors_health_errors_and_docs(self):
        response = self.client.options('/api/auth/login', headers={'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'Content-Type, Authorization'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['access-control-allow-origin'], 'http://localhost:5173')
        malformed = self.client.post('/api/auth/login', content='{', headers={'Content-Type': 'application/json'})
        self.assertEqual(malformed.status_code, 400)
        self.assertEqual(malformed.json(), {'error': 'JSON inválido.'})
        self.assertEqual(self.client.get('/api/health').json(), {'status': 'ok', 'database': 'postgresql'})
        self.assertEqual(self.client.get('/missing').status_code, 404)
        self.assertIn('/api/orders', self.client.get('/openapi.json').json()['paths'])
        self.assertEqual(self.client.get('/docs').status_code, 200)
        self.assertIsNone(read_token('invalid', self.settings.secret))


if __name__ == '__main__':
    unittest.main()
