import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.db import get_db
from core.permissions import (
    Audience, DocumentAccess, assistant_can, can_approve_document,
    can_read_document, can_read_ticket, can_submit_document,
)
from core.security import get_current_user
from routes.auth import router
from scripts.seed_users import USERS, seed_users


def user(name):
    row = next(row for row in USERS if row[0] == name)
    return SimpleNamespace(id=uuid4(), name=name, department=row[1], user_type=row[2],
                           groups=list(row[3]), support_departments=list(row[4]), is_active=True)


class PermissionTests(unittest.TestCase):
    def test_department_and_company_access(self):
        doc = DocumentAccess('finance', Audience.DEPARTMENT, 'published')
        self.assertFalse(can_read_document(user('Alice'), doc))
        self.assertTrue(can_read_document(user('David'), doc))
        self.assertTrue(can_read_document(user('Alice'), replace(doc, audience=Audience.COMPANY)))

    def test_restricted_has_no_role_bypass(self):
        doc = DocumentAccess('finance', Audience.RESTRICTED, 'published', ('finance_employees',))
        for name in ('Alice', 'Henry', 'Iris', 'Grace'):
            with self.subTest(name=name):
                self.assertFalse(can_read_document(user(name), doc))
        david = user('David')
        self.assertTrue(can_read_document(david, doc))
        david.groups = []
        self.assertFalse(can_read_document(david, doc))
        self.assertFalse(can_read_document(user('David'), replace(doc, allowed_groups=())))

    def test_unpublished_and_inactive_denied(self):
        doc = DocumentAccess('engineering', Audience.COMPANY, 'published')
        for state in ('draft', 'review', 'rejected'):
            self.assertFalse(can_read_document(user('Alice'), replace(doc, status=state)))
        alice = user('Alice')
        alice.is_active = False
        self.assertFalse(can_read_document(alice, doc))
        self.assertFalse(assistant_can(alice, 'search_documents'))

    def test_publisher_scope_and_audience(self):
        doc = DocumentAccess('engineering', Audience.DEPARTMENT)
        self.assertTrue(can_submit_document(user('Bob'), doc))
        self.assertFalse(can_submit_document(user('Emma'), doc))
        self.assertFalse(can_submit_document(user('Alice'), doc))
        self.assertFalse(can_submit_document(user('Bob'), replace(doc, audience=Audience.COMPANY)))
        self.assertFalse(can_submit_document(user('Bob'), replace(doc, status='published')))
        doc = DocumentAccess('finance', Audience.RESTRICTED, allowed_groups=('finance_employees',))
        self.assertTrue(can_submit_document(user('Emma'), doc))
        self.assertFalse(can_submit_document(user('Emma'), replace(doc, allowed_groups=('security',))))

    def test_approval_scope_state_and_identity(self):
        carol = user('Carol')
        doc = DocumentAccess('engineering', Audience.DEPARTMENT, 'review', submitted_by=uuid4())
        self.assertTrue(can_approve_document(carol, doc))
        self.assertFalse(can_approve_document(user('Frank'), doc))
        self.assertFalse(can_approve_document(user('Bob'), doc))
        self.assertFalse(can_approve_document(carol, replace(doc, status='draft')))
        self.assertFalse(can_approve_document(carol, replace(doc, submitted_by=carol.id)))
        self.assertFalse(can_approve_document(carol, replace(doc, submitted_by=None)))

    def test_support_scope_and_ticket_ownership(self):
        grace, alice = user('Grace'), user('Alice')
        doc = DocumentAccess('finance', Audience.SUPPORT, 'published')
        self.assertTrue(can_read_document(grace, doc))
        self.assertFalse(can_read_document(user('Henry'), doc))
        self.assertTrue(can_read_ticket(alice, requester_id=alice.id, department='engineering'))
        self.assertFalse(can_read_ticket(alice, requester_id=uuid4(), department='engineering'))
        self.assertTrue(can_read_ticket(grace, requester_id=uuid4(), department='finance'))
        grace.support_departments = []
        self.assertFalse(can_read_document(grace, doc))
        self.assertFalse(can_read_ticket(grace, requester_id=uuid4(), department='finance'))

    def test_assistant_denies_privileged_and_unknown_tools(self):
        for operation in ('publish_document', 'change_permissions', 'update_ticket', 'unknown'):
            self.assertFalse(assistant_can(user('Henry'), operation))


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(router)
        self.db = AsyncMock()
        async def db_override():
            yield self.db
        self.app.dependency_overrides[get_db] = db_override
        self.client = TestClient(self.app)
        self.payload = dict(name='New User', email='new@example.com', password='long-test-password',
                            department='finance', user_type='platform_administrator')

    def test_anonymous_cannot_register(self):
        for path in ('/auth/register', '/auth/signup'):
            self.assertEqual(self.client.post(path, json=self.payload).status_code, 401)
        self.db.execute.assert_not_awaited()

    def test_employee_cannot_self_promote(self):
        self.app.dependency_overrides[get_current_user] = lambda: user('Alice')
        self.assertEqual(self.client.post('/auth/register', json=self.payload).status_code, 403)
        self.db.execute.assert_not_awaited()

    def test_admin_creates_account_without_impersonation_token(self):
        from datetime import datetime, timezone
        from unittest.mock import Mock
        self.app.dependency_overrides[get_current_user] = lambda: user('Henry')
        result = Mock()
        result.scalar_one_or_none.return_value = None
        self.db.execute.return_value = result
        self.db.add = Mock()

        async def refresh(account):
            account.id = uuid4()
            account.created_at = account.updated_at = datetime.now(timezone.utc)
            account.last_login = None
        self.db.refresh.side_effect = refresh
        response = self.client.post('/auth/register', json=self.payload)
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()['user_type'], 'platform_administrator')
        self.assertNotIn('token', response.json())
        self.assertNotIn('hashed_password', response.json())
        self.assertNotEqual(self.db.add.call_args.args[0].hashed_password, self.payload['password'])

    def test_inactive_admin_denied(self):
        henry = user('Henry')
        henry.is_active = False
        self.app.dependency_overrides[get_current_user] = lambda: henry
        self.assertEqual(self.client.post('/auth/register', json=self.payload).status_code, 403)


class SeedTests(unittest.IsolatedAsyncioTestCase):
    async def test_existing_accounts_are_not_overwritten(self):
        db = AsyncMock()
        db.scalar.return_value = object()
        self.assertEqual(await seed_users(db, 'long-test-password'), 0)
        db.add.assert_not_called()

    async def test_all_nine_accounts_created(self):
        db = AsyncMock()
        db.scalar.return_value = None
        from unittest.mock import Mock
        db.add = Mock()
        with patch('scripts.seed_users.hash_password', return_value='hashed'):
            self.assertEqual(await seed_users(db, 'long-test-password'), 9)
        accounts = [call.args[0] for call in db.add.call_args_list]
        self.assertEqual(len({account.email for account in accounts}), 9)
        self.assertTrue(all(account.hashed_password == 'hashed' for account in accounts))


if __name__ == '__main__':
    unittest.main()
