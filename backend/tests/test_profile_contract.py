"""Focused legacy profile/follow contracts without starting the application.

Load real endpoint bodies through the existing isolated auth-test loader. These
tests exercise request models, ownership, persistence and public response shapes;
they do not contact Mongo, a mail service or the deployed application.
"""
import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest

from fastapi import HTTPException

from test_account_recovery import MemoryUsers, load_auth_slice, request


def load_profile_slice():
    namespace = load_auth_slice()
    source = Path(__file__).resolve().parents[1] / "server.py"
    names = {
        "ProfileUpdate", "ExistingProfileUpdate", "update_user_profile",
        "get_user_profile", "get_user_followers", "get_user_following",
        "get_follow_status",
    }
    selected = []
    for node in ast.parse(source.read_text()).body:
        if isinstance(node, (ast.ClassDef, ast.AsyncFunctionDef)) and node.name in names:
            node.decorator_list = []
            selected.append(node)
    # Both POST and PUT have the same legacy function name. The final definition
    # is the identity-edit PUT endpoint whose request model this regression covers.
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(source), "exec"), namespace)
    return namespace


class AsyncDocuments:
    def __init__(self, documents):
        self.documents = documents

    def __aiter__(self):
        async def iterate():
            for document in self.documents:
                yield deepcopy(document)
        return iterate()


class SocialUsers(MemoryUsers):
    def find(self, filters=None):
        ids = (filters or {}).get("id", {}).get("$in", [])
        return AsyncDocuments([doc for doc in self.documents if doc["id"] in ids])


class ProfileContractTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.n = load_profile_slice()
        self.users = SocialUsers([
            {"id": "member", "username": "learner", "email": "old@example.test",
             "status": "approved", "real_name": "Old Name", "following": ["mentor"],
             "active_session_id": "member-session", "password_hash": "private-hash"},
            {"id": "mentor", "username": "mentor", "email": "mentor@example.test",
             "status": "approved", "followers": ["member"], "follower_count": 1,
             "active_session_id": "mentor-private-session", "reset_token_hash": "private-reset"},
            {"id": "other", "username": "other", "email": "other@example.test"},
        ])
        self.n["db"] = SimpleNamespace(users=self.users)

    async def test_identity_edit_accepts_expected_fields_and_keeps_session_private(self):
        endpoint = self.n["update_user_profile"]
        model = endpoint.__annotations__["profile_data"]
        self.assertIs(model, self.n["ExistingProfileUpdate"])
        body = model(real_name="New Name", screen_name="Student", username="student",
                     email="new@example.test", active_session_id="attacker-session", bio="ignored")
        response = await endpoint(
            request({"X-User-ID": "member", "X-Session-ID": "member-session"}), "member", body
        )
        changed = self.users.documents[0]
        for field, value in {"real_name": "New Name", "screen_name": "Student", "username": "student", "email": "new@example.test"}.items():
            self.assertEqual(changed[field], value)
        self.assertEqual(changed["active_session_id"], "member-session")
        self.assertNotIn("bio", changed)
        self.assertNotIn("active_session_id", response.model_dump())
        self.assertNotIn("password_hash", response.model_dump())

    async def test_identity_edit_still_requires_the_owners_session(self):
        body = self.n["ExistingProfileUpdate"](email="changed@example.test")
        for headers in ({}, {"X-User-ID": "mentor", "X-Session-ID": "mentor-private-session"},
                        {"X-User-ID": "member", "X-Session-ID": "wrong-session"}):
            with self.assertRaises(HTTPException) as caught:
                await self.n["update_user_profile"](request(headers), "member", body)
            self.assertIn(caught.exception.status_code, (401, 403))
        self.assertEqual(self.users.writes, 0)

    async def test_follow_status_has_explicit_boolean_in_both_directions(self):
        self.assertEqual(await self.n["get_follow_status"]("member", "mentor"), {"is_following": True})
        self.assertEqual(await self.n["get_follow_status"]("member", "other"), {"is_following": False})
        self.assertEqual(await self.n["get_follow_status"]("mentor", "member"), {"is_following": False})

    async def test_follow_lists_have_safe_profile_objects_and_empty_shape(self):
        following = await self.n["get_user_following"]("member")
        followers = await self.n["get_user_followers"]("mentor")
        self.assertEqual([item["id"] for item in following["following"]], ["mentor"])
        self.assertEqual([item["id"] for item in followers["followers"]], ["member"])
        self.assertEqual(following["count"], 1)
        self.assertEqual(followers["count"], 1)
        for item in following["following"] + followers["followers"]:
            self.assertFalse({"email", "active_session_id", "password_hash", "reset_token_hash"} & item.keys())
        self.assertEqual(await self.n["get_user_following"]("other"), {"following": [], "count": 0})
        profile = await self.n["get_user_profile"](request(), "mentor")
        self.assertEqual(profile["follower_count"], 1)
        self.assertNotIn("followers", profile)
        self.assertNotIn("following", profile)


if __name__ == "__main__":
    unittest.main()
