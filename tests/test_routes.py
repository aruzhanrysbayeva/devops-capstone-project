"""
Account API Service Test Suite

Test cases can be run with the following:
  nosetests -v --with-spec --spec-color
  coverage report -m
"""
import os
import logging
from unittest import TestCase
from unittest.mock import patch
from tests.factories import AccountFactory
from service.common import status  # HTTP Status Codes
from service.models import db, Account, init_db
from service.routes import app

DATABASE_URI = os.getenv(
    "DATABASE_URI", "postgresql://postgres:postgres@localhost:5432/postgres"
)

BASE_URL = "/accounts"


######################################################################
#  T E S T   C A S E S
######################################################################
class TestAccountService(TestCase):
    """Account Service Tests"""

    @classmethod
    def setUpClass(cls):
        """Run once before all tests"""
        app.config["TESTING"] = True
        app.config["DEBUG"] = False
        app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
        app.logger.setLevel(logging.CRITICAL)
        init_db(app)

    @classmethod
    def tearDownClass(cls):
        """Runs once before test suite"""

    def setUp(self):
        """Runs before each test"""
        db.session.query(Account).delete()  # clean up the last tests
        db.session.commit()

        self.client = app.test_client()

    def tearDown(self):
        """Runs once after each test case"""
        db.session.remove()

    ######################################################################
    #  H E L P E R   M E T H O D S
    ######################################################################

    def _create_accounts(self, count):
        """Factory method to create accounts in bulk"""
        accounts = []
        for _ in range(count):
            account = AccountFactory()
            response = self.client.post(BASE_URL, json=account.serialize())
            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
                "Could not create test Account",
            )
            new_account = response.get_json()
            account.id = new_account["id"]
            accounts.append(account)
        return accounts

    ######################################################################
    #  A C C O U N T   T E S T   C A S E S
    ######################################################################

    def test_index(self):
        """It should get 200_OK from the Home Page"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_health(self):
        """It should be healthy"""
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "OK")

    def test_create_account(self):
        """It should Create a new Account"""
        account = AccountFactory()
        response = self.client.post(
            BASE_URL,
            json=account.serialize(),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Make sure location header is set
        location = response.headers.get("Location", None)
        self.assertIsNotNone(location)

        # Check the data is correct
        new_account = response.get_json()
        self.assertEqual(new_account["name"], account.name)
        self.assertEqual(new_account["email"], account.email)
        self.assertEqual(new_account["address"], account.address)
        self.assertEqual(new_account["phone_number"], account.phone_number)
        self.assertEqual(new_account["date_joined"], str(account.date_joined))

    def test_bad_request(self):
        """It should not Create an Account when sending the wrong data"""
        response = self.client.post(BASE_URL, json={"name": "not enough data"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unsupported_media_type(self):
        """It should not Create an Account when sending the wrong media type"""
        account = AccountFactory()
        response = self.client.post(
            BASE_URL,
            json=account.serialize(),
            content_type="test/html"
        )
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    def test_read_account(self):
        """It should read a persisted account and return all its fields"""
        account = self._create_accounts(1)[0]
        response = self.client.get(f"{BASE_URL}/{account.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get_json(), account.serialize())

    def test_read_missing_account(self):
        """It should return a JSON 404 for an unknown account"""
        response = self.client.get(f"{BASE_URL}/0")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.get_json()["status"], 404)

    def test_list_accounts(self):
        """It should list every persisted account"""
        accounts = self._create_accounts(3)
        response = self.client.get(BASE_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual({a["id"] for a in response.get_json()}, {a.id for a in accounts})

    def test_list_empty_accounts(self):
        """It should return an empty collection with 200, never 404"""
        response = self.client.get(BASE_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get_json(), [])

    def test_update_account(self):
        """It should persist updates while retaining the account ID"""
        account = self._create_accounts(1)[0]
        data = account.serialize()
        data["phone_number"] = "555-1111"
        response = self.client.put(f"{BASE_URL}/{account.id}", json=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get_json(), data)
        self.assertEqual(self.client.get(f"{BASE_URL}/{account.id}").get_json(), data)

    def test_update_missing_account(self):
        """It should not create an account while updating an unknown ID"""
        response = self.client.put(f"{BASE_URL}/0", json=AccountFactory().serialize())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Account.all(), [])

    def test_update_invalid_account(self):
        """It should reject an incomplete update and retain persisted data"""
        account = self._create_accounts(1)[0]
        original = account.serialize()
        response = self.client.put(f"{BASE_URL}/{account.id}", json={"name": "bad"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        db.session.rollback()
        self.assertEqual(self.client.get(f"{BASE_URL}/{account.id}").get_json(), original)

    def test_update_wrong_media(self):
        """It should reject non-JSON updates"""
        account = self._create_accounts(1)[0]
        response = self.client.put(f"{BASE_URL}/{account.id}", data="hello", content_type="text/plain")
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    def test_delete_account(self):
        """It should delete the account and return no response body"""
        account = self._create_accounts(1)[0]
        response = self.client.delete(f"{BASE_URL}/{account.id}")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(response.data, b"")
        self.assertIsNone(Account.find(account.id))

    def test_delete_missing_account(self):
        """It should make deletion idempotent for an unknown account"""
        response = self.client.delete(f"{BASE_URL}/0")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(response.data, b"")

    def test_method_not_allowed(self):
        """It should reject unsupported collection methods"""
        response = self.client.delete(BASE_URL)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_create_location_resolves_to_account(self):
        """It should identify the newly created resource in Location"""
        response = self.client.post(BASE_URL, json=AccountFactory().serialize())
        location = response.headers["Location"]
        self.assertTrue(location.endswith(f"{BASE_URL}/{response.get_json()['id']}"))
        self.assertEqual(self.client.get(location).get_json(), response.get_json())

    def test_create_optional_fields(self):
        """It should supply today's date when optional inputs are omitted"""
        from datetime import date
        data = {"name": "Test Account", "email": "test@example.invalid", "address": "Test Street"}
        response = self.client.post(BASE_URL, json=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(response.get_json()["phone_number"])
        self.assertEqual(response.get_json()["date_joined"], date.today().isoformat())

    def test_json_with_charset(self):
        """It should accept a JSON media type with a charset parameter"""
        response = self.client.post(BASE_URL, json=AccountFactory().serialize(),
                                    content_type="application/json; charset=utf-8")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_unexpected_failure_is_json(self):
        """It should return the documented JSON error format on server failure"""
        previous = app.config.get("PROPAGATE_EXCEPTIONS")
        app.config["PROPAGATE_EXCEPTIONS"] = False
        try:
            with patch("service.routes.Account.all", side_effect=RuntimeError("test failure")):
                response = self.client.get(BASE_URL)
            self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
            self.assertEqual(response.get_json()["error"], "Internal Server Error")
        finally:
            app.config["PROPAGATE_EXCEPTIONS"] = previous
