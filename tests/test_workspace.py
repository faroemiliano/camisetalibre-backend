import copy
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select

from test_api import DatabaseCase
from app.db.models import CustomerPreferences, EditorWorkspace, Project

IMAGE = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aK1sAAAAASUVORK5CYII='


def document():
    colors = {'base': '#ffffff', 'sleeves': '#123d72', 'collar': '#123d72', 'detail': '#75c7e8', 'accent': '#33aa55'}
    rect = {'id': 'rect-1', 'type': 'rect', 'x': 100, 'y': 200, 'rotation': 12, 'width': 120, 'height': 80, 'fill': '#abcdef'}
    text = {'id': 'name-1', 'type': 'text', 'role': 'name', 'x': 200, 'y': 300, 'rotation': 0,
            'text': 'MI EQUIPO', 'width': 320, 'fontSize': 40, 'fontFamily': 'Impact',
            'fill': '#ffffff', 'outline': '#000000', 'outlineWidth': 2}
    logo = {'id': 'logo-1', 'type': 'image', 'role': 'logo', 'x': 300, 'y': 400, 'rotation': 0,
            'width': 90, 'height': 100, 'original': IMAGE, 'removeBackground': True,
            'tolerance': 20, 'interior': True, 'tint': None, 'outline': '#ffffff', 'outlineWidth': 1}
    line = {'id': 'line-1', 'type': 'line', 'x': 20, 'y': 30, 'rotation': -12, 'length': 200, 'stroke': '#00aa55', 'strokeWidth': 10}
    objects = {'shirt': {'front': [rect, logo], 'back': [text]}, 'short': {'front': [line], 'back': []}}
    state = {'model': 'polo', 'colors': {'shirt': colors, 'short': dict(colors)}, 'objects': objects}
    return {'version': 2, **copy.deepcopy(state), 'pattern': 'catalog-01', 'designSource': 'catalog',
            'customDesign': {'front': IMAGE}, 'catalogPalettes': {'catalog-01': colors},
            'designStates': {'custom': copy.deepcopy(state)},
            'patternSettings': {'diagonal': {'width': 66, 'gap': 85, 'angle': -28, 'offset': 0, 'position': 330, 'accentWidth': 7}}}


class WorkspaceTests(DatabaseCase):
    def payload(self, revision=0):
        return {'document': document(), 'ui': {'side': 'back', 'product': 'short', 'activeTool': 'properties'}, 'expectedRevision': revision}

    def test_full_workspace_round_trip_and_customer_isolation(self):
        first = self.headers()
        second = self.headers('otro@example.test')
        self.assertEqual(self.client.get('/api/customers/me/workspace', headers=first).json(), {'workspace': None})
        response = self.client.put('/api/customers/me/workspace', headers=first, json=self.payload())
        self.assertEqual(response.status_code, 200, response.text)
        workspace = response.json()['workspace']
        self.assertEqual(workspace['document'], document())
        self.assertEqual(workspace['ui'], self.payload()['ui'])
        self.assertEqual(workspace['revision'], 1)
        self.assertEqual(self.client.get('/api/customers/me/workspace', headers=second).json(), {'workspace': None})
        self.assertEqual(self.client.get('/api/projects', headers=second).json(), {'projects': []})
        projects = self.client.get('/api/projects', headers=first).json()['projects']
        self.assertEqual(projects[0]['id'], workspace['projectId'])
        self.assertEqual(projects[0]['design'], document())
        with self.db.sessions() as session:
            stored = session.get(Project, workspace['projectId'])
            self.assertEqual(stored.design['objects']['shirt']['front'][1]['original'], IMAGE)
            self.assertEqual(stored.design['designStates']['custom']['objects']['shirt']['back'][0]['text'], 'MI EQUIPO')
        self.assertEqual(self.count(EditorWorkspace), 1)

    def test_workspace_revisions_prevent_lost_updates(self):
        headers = self.headers()
        first = self.client.put('/api/customers/me/workspace', headers=headers, json=self.payload()).json()['workspace']
        changed = self.payload(1)
        changed['document']['objects']['shirt']['back'][0]['text'] = 'ACTUALIZADO'
        response = self.client.put('/api/customers/me/workspace', headers=headers, json=changed)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['workspace']['revision'], 2)
        self.assertEqual(response.json()['workspace']['projectId'], first['projectId'])
        self.assertEqual(self.client.put('/api/customers/me/workspace', headers=headers, json=self.payload(1)).status_code, 409)
        loaded = self.client.get('/api/customers/me/workspace', headers=headers).json()['workspace']
        self.assertEqual(loaded['document']['objects']['shirt']['back'][0]['text'], 'ACTUALIZADO')
        self.assertEqual(self.count(Project), 1)

    def test_concurrent_initial_workspace_save_creates_only_one_project(self):
        headers = self.headers()
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(lambda _: self.client.put('/api/customers/me/workspace', headers=headers, json=self.payload()).status_code, range(2)))
        self.assertEqual(sorted(statuses), [200, 409])
        self.assertEqual(self.count(EditorWorkspace), 1)
        self.assertEqual(self.count(Project), 1)

    def test_cannot_choose_owner_or_link_foreign_project(self):
        first = self.headers()
        second = self.headers('otro@example.test')
        saved = self.client.put('/api/customers/me/workspace', headers=first, json=self.payload()).json()['workspace']
        for key, value in (('customerId', 'other'), ('ownerId', 'other'), ('projectId', saved['projectId'])):
            body = self.payload()
            body[key] = value
            self.assertEqual(self.client.put('/api/customers/me/workspace', headers=second, json=body).status_code, 422)
        self.assertEqual(self.count(EditorWorkspace), 1)
        self.assertEqual(self.client.get('/api/customers/me/workspace', headers=second).json(), {'workspace': None})

    def test_document_validation_rejects_unsafe_or_unloadable_data(self):
        headers = self.headers()
        bad_documents = []
        wrong_version = document(); wrong_version['version'] = 1; bad_documents.append(wrong_version)
        remote_image = document(); remote_image['objects']['shirt']['front'][1]['original'] = 'https://example.test/logo.svg'; bad_documents.append(remote_image)
        duplicate = document(); duplicate['objects']['shirt']['back'][0]['id'] = 'rect-1'; bad_documents.append(duplicate)
        unknown_pattern = document(); unknown_pattern['pattern'] = 'catalog-99'; bad_documents.append(unknown_pattern)
        invalid_color = document(); invalid_color['colors']['shirt']['base'] = 'red'; bad_documents.append(invalid_color)
        missing_side = document(); del missing_side['objects']['short']['back']; bad_documents.append(missing_side)
        null_optional = document(); null_optional['designSource'] = None; bad_documents.append(null_optional)
        for item in bad_documents:
            body = self.payload(); body['document'] = item
            self.assertEqual(self.client.put('/api/customers/me/workspace', headers=headers, json=body).status_code, 422)
        self.assertEqual(self.count(Project), 0)

    def test_project_updates_invalidate_old_workspace_revision(self):
        headers = self.headers()
        saved = self.client.put('/api/customers/me/workspace', headers=headers, json=self.payload()).json()['workspace']
        response = self.client.put('/api/projects/' + saved['projectId'], headers=headers, json={'name': 'Mi conjunto personalizado'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.put('/api/customers/me/workspace', headers=headers, json=self.payload(1)).status_code, 409)

    def test_budget_preferences_are_persisted_per_customer(self):
        first = self.headers()
        second = self.headers('otro@example.test')
        body = {'budget': {'productId': 'chomba', 'fabricId': 'premium', 'quantity': 12}, 'expectedRevision': 0}
        result = self.client.put('/api/customers/me/preferences', headers=first, json=body)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['preferences']['budget'], body['budget'])
        self.assertEqual(result.json()['preferences']['revision'], 1)
        self.assertEqual(self.client.get('/api/customers/me/preferences', headers=second).json(), {'preferences': None})
        self.assertEqual(self.client.get('/api/customers/me/preferences', headers=first).json()['preferences']['budget'], body['budget'])
        self.assertEqual(self.client.put('/api/customers/me/preferences', headers=first, json=body).status_code, 409)
        body['expectedRevision'] = 1; body['budget']['quantity'] = 20
        self.assertEqual(self.client.put('/api/customers/me/preferences', headers=first, json=body).json()['preferences']['revision'], 2)
        self.assertEqual(self.count(CustomerPreferences), 1)

    def test_preferences_validate_catalog_and_quantity(self):
        headers = self.headers()
        for product, fabric, quantity in (('missing', 'eco', 8), ('camiseta', 'missing', 8), ('short', 'pro', 7), ('short', 'pro', 0)):
            result = self.client.put('/api/customers/me/preferences', headers=headers, json={
                'budget': {'productId': product, 'fabricId': fabric, 'quantity': quantity}, 'expectedRevision': 0})
            self.assertEqual(result.status_code, 422)
        self.assertEqual(self.count(CustomerPreferences), 0)

    def test_workspace_and_preferences_require_authentication(self):
        for path in ('workspace', 'preferences'):
            self.assertEqual(self.client.get('/api/customers/me/' + path).status_code, 401)
            self.assertEqual(self.client.put('/api/customers/me/' + path, json={}).status_code, 401)
