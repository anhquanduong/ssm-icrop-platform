import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
import sqlite3

# Add 'app' directory to Python system path to resolve imports properly
workspace_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
app_dir = os.path.join(workspace_dir, "app")
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

# Override DatabaseManager db_path before import if possible, or we can use a custom db file path
from utils.db_manager import DatabaseManager
import utils.auth_secure as auth_secure

class TestSecureAuthentication(unittest.TestCase):
    def setUp(self):
        # Create a temporary database for testing to ensure isolated tests
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        
        # Override the database manager to point to our test database
        # We subclass or patch auth_secure and DatabaseManager to use self.temp_db_path
        self.db = DatabaseManager(db_path=self.temp_db_path)
        
        # Patch DatabaseManager instantiation inside auth_secure to use our test path
        # Since auth_secure instantiates DatabaseManager() directly, we can override the default path
        # by temporarily monkeypatching DatabaseManager.__init__ or keeping the default path.
        # But wait, DatabaseManager.__init__ accepts a db_path or defaults to it.
        # Let's monkeypatch DatabaseManager.__init__ so any new instance uses our temp path.
        self.original_init = DatabaseManager.__init__
        temp_path = self.temp_db_path
        def patched_init(inner_self, db_path=None):
            self.original_init(inner_self, db_path=temp_path)
        DatabaseManager.__init__ = patched_init
        
        # Clear simulator mailbox
        auth_secure.LOCAL_MAILBOX_SIMULATOR.clear()

    def tearDown(self):
        # Restore DatabaseManager.__init__
        DatabaseManager.__init__ = self.original_init
        
        # Trigger garbage collection to release SQLite file handles
        import gc
        gc.collect()
        
        # Close and remove the temporary database file safely
        try:
            os.close(self.temp_db_fd)
        except Exception:
            pass
            
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except Exception as teardown_err:
                # Log warning but do not crash the tests if Windows locks the temp file
                print(f"Teardown clean-up warning: {teardown_err}")

    def test_01_user_registration_validation(self):
        """Assert registration inputs and check that verify tokens are generated properly."""
        # Test short username
        success, msg = auth_secure.register_secure_user(
            username="ur", email="ur@test.com", password="password123", name="User Registration", workplace="Work"
        )
        self.assertFalse(success)
        self.assertIn("Username", msg)

        # Test invalid email
        success, msg = auth_secure.register_secure_user(
            username="user_reg", email="invalid_email", password="password123", name="User Registration", workplace="Work"
        )
        self.assertFalse(success)
        self.assertIn("email", msg)

        # Test short password
        success, msg = auth_secure.register_secure_user(
            username="user_reg", email="ur@test.com", password="123", name="User Registration", workplace="Work"
        )
        self.assertFalse(success)
        self.assertIn("Password", msg)

        # Test empty name
        success, msg = auth_secure.register_secure_user(
            username="user_reg", email="ur@test.com", password="password123", name="", workplace="Work"
        )
        self.assertFalse(success)
        self.assertIn("Full Name", msg)

        # Test successful registration
        success, msg = auth_secure.register_secure_user(
            username="user_reg", email="ur@test.com", password="password123", name="User Registration", workplace="BOKU"
        )
        self.assertTrue(success)
        self.assertIn("verification link", msg.lower())

        # Verify database record
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, email, is_verified, verification_token, token_expiry FROM users WHERE username = 'user_reg'")
            row = cursor.fetchone()
            self.assertIsNotNone(row)
            uid, uname, uemail, is_verified, token, expiry = row
            self.assertEqual(uname, "user_reg")
            self.assertEqual(uemail, "ur@test.com")
            self.assertEqual(is_verified, 0)
            self.assertIsNotNone(token)
            self.assertIsNotNone(expiry)

        # Assert offline email simulator cached the activation email and link
        self.assertEqual(len(auth_secure.LOCAL_MAILBOX_SIMULATOR), 1)
        sent_mail = auth_secure.LOCAL_MAILBOX_SIMULATOR[0]
        self.assertEqual(sent_mail["to"], "ur@test.com")
        self.assertIn("Verify Your BOKU", sent_mail["subject"])
        self.assertIn("http://localhost:8501/?verify_token=", sent_mail["body_html"])

        # Test duplicate username or email registration
        success_dup, msg_dup = auth_secure.register_secure_user(
            username="user_reg", email="different@test.com", password="password123", name="Dup", workplace="Work"
        )
        self.assertFalse(success_dup)
        self.assertIn("Username", msg_dup)

        success_dup_email, msg_dup_email = auth_secure.register_secure_user(
            username="diff_user", email="ur@test.com", password="password123", name="Dup", workplace="Work"
        )
        self.assertFalse(success_dup_email)
        self.assertIn("Email", msg_dup_email)

    def test_02_email_verification_flow(self):
        """Assert email verification token match, expired token regeneration, and status updates."""
        # Register a pending user
        auth_secure.register_secure_user(
            username="verify_tester", email="vt@test.com", password="password123", name="Verify Tester", workplace="BOKU"
        )
        
        # Get verification token from DB
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT verification_token FROM users WHERE username = 'verify_tester'")
            token = cursor.fetchone()[0]

        # Test verify with invalid token
        success, msg = auth_secure.verify_user_email_token("fake_token_123")
        self.assertFalse(success)
        self.assertIn("invalid", msg.lower())

        # Test verify with expired token
        # Manually force expiry timestamp into the past in the database
        past_expiry = (datetime.now() - timedelta(hours=2)).isoformat()
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET token_expiry = ? WHERE username = 'verify_tester'", (past_expiry,))
            conn.commit()

        success, msg = auth_secure.verify_user_email_token(token)
        self.assertFalse(success)
        self.assertIn("expired", msg.lower())

        # Check that a new token and expiry were generated
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT verification_token, token_expiry FROM users WHERE username = 'verify_tester'")
            new_token, new_expiry = cursor.fetchone()
            self.assertNotEqual(new_token, token)
            self.assertGreater(datetime.fromisoformat(new_expiry), datetime.now())

        # Test successful verification with the new valid token
        success, msg = auth_secure.verify_user_email_token(new_token)
        self.assertTrue(success)
        self.assertIn("activated", msg.lower())

        # Assert verification columns are cleaned and updated in DB
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT is_verified, verification_token, token_expiry FROM users WHERE username = 'verify_tester'")
            is_verified, token_val, expiry_val = cursor.fetchone()
            self.assertEqual(is_verified, 1)
            self.assertIsNone(token_val)
            self.assertIsNone(expiry_val)

    def test_03_progressive_lockout_and_sign_in(self):
        """Assert authentication limits, progressive lockout blockings, and successful logins."""
        username = "auth_tester"
        password = "secret_password"
        
        # Register and verify account
        auth_secure.register_secure_user(
            username=username, email="at@test.com", password=password, name="Auth Tester", workplace="BOKU"
        )
        with self.db.get_connection() as conn:
            conn.execute("UPDATE users SET is_verified = 1 WHERE username = ?", (username,))
            conn.commit()

        # Attempt to log in with wrong username (Timing mask check)
        success, msg, payload = auth_secure.authenticate_secure_user("nonexistent_user", "password")
        self.assertFalse(success)
        self.assertIn("Invalid", msg)
        self.assertIsNone(payload)

        # Attempt 1 failed login
        success, msg, payload = auth_secure.authenticate_secure_user(username, "wrong_pass_1")
        self.assertFalse(success)
        self.assertIn("Attempt 1", msg)
        
        # Failed logins 2, 3, 4
        for i in range(2, 5):
            success, msg, payload = auth_secure.authenticate_secure_user(username, f"wrong_pass_{i}")
            self.assertFalse(success)
            self.assertIn(f"Attempt {i}", msg)

        # Attempt 5 failed login (exceeds threshold) - Should lock user out
        success, msg, payload = auth_secure.authenticate_secure_user(username, "wrong_pass_5")
        self.assertFalse(success)
        self.assertIn("locked for 15 minutes", msg.lower())
        self.assertIsNone(payload)

        # Confirm lockout timestamp is written to database
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT login_attempts, lockout_until FROM users WHERE username = ?", (username,))
            attempts, lockout = cursor.fetchone()
            self.assertEqual(attempts, 5)
            self.assertIsNotNone(lockout)
            self.assertGreater(datetime.fromisoformat(lockout), datetime.now())

        # Immediate login rejection check: attempting correct password during active lockout should reject instantly
        success, msg, payload = auth_secure.authenticate_secure_user(username, password)
        self.assertFalse(success)
        self.assertIn("locked", msg.lower())
        self.assertIsNone(payload)

        # Simulate lockout expiration by clearing lockout_until/attempts manually
        with self.db.get_connection() as conn:
            conn.execute("UPDATE users SET login_attempts = 0, lockout_until = NULL WHERE username = ?", (username,))
            conn.commit()

        # Attempt correct password after lockout cleared - should succeed
        success, msg, payload = auth_secure.authenticate_secure_user(username, password)
        self.assertTrue(success)
        self.assertEqual(payload["username"], username)
        self.assertEqual(payload["is_verified"], 1)
        self.assertIsNotNone(payload["session_token"])
        
        # Check failed attempts reset in DB
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT login_attempts, lockout_until FROM users WHERE username = ?", (username,))
            attempts, lockout = cursor.fetchone()
            self.assertEqual(attempts, 0)
            self.assertIsNone(lockout)

    def test_04_password_recovery_and_resets(self):
        """Assert password reset token generation, 1-hour expiry, and hash overrides."""
        username = "recovery_tester"
        email = "rt@test.com"
        password = "old_password"
        new_password = "super_secure_new_password"
        
        # Register and verify account
        auth_secure.register_secure_user(
            username=username, email=email, password=password, name="Recovery Tester", workplace="BOKU"
        )
        with self.db.get_connection() as conn:
            conn.execute("UPDATE users SET is_verified = 1 WHERE username = ?", (username,))
            conn.commit()

        # Test request reset for unregistered email (Anti-harvesting test)
        # Should return success message but log warning and send no real simulator emails
        auth_secure.LOCAL_MAILBOX_SIMULATOR.clear()
        success, msg = auth_secure.request_password_reset("unregistered@test.com")
        self.assertTrue(success)
        self.assertIn("dispatched", msg.lower())
        # The unmapped email address warning is logged, and no email is sent for safety
        # (Wait, auth_secure.request_password_reset does not call send_system_email if row is None,
        # so LOCAL_MAILBOX_SIMULATOR length remains 0)
        self.assertEqual(len(auth_secure.LOCAL_MAILBOX_SIMULATOR), 0)

        # Test request reset for valid email
        success, msg = auth_secure.request_password_reset(email)
        self.assertTrue(success)
        self.assertIn("dispatched", msg.lower())
        self.assertEqual(len(auth_secure.LOCAL_MAILBOX_SIMULATOR), 1)
        
        # Inspect reset email payload and extract token
        sent_mail = auth_secure.LOCAL_MAILBOX_SIMULATOR[0]
        self.assertEqual(sent_mail["to"], email)
        self.assertIn("Password Reset Request", sent_mail["subject"])
        
        # Extract reset_token from DB
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT reset_token, token_expiry FROM users WHERE username = ?", (username,))
            token, expiry = cursor.fetchone()
            self.assertIsNotNone(token)
            self.assertIsNotNone(expiry)

        # Test execute password reset with invalid token
        success, msg = auth_secure.execute_password_reset_token("fake_reset_token", new_password)
        self.assertFalse(success)
        self.assertIn("invalid", msg.lower())

        # Test execute password reset with expired token
        past_expiry = (datetime.now() - timedelta(minutes=5)).isoformat()
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET token_expiry = ? WHERE username = ?", (past_expiry, username))
            conn.commit()
            
        success, msg = auth_secure.execute_password_reset_token(token, new_password)
        self.assertFalse(success)
        self.assertIn("expired", msg.lower())

        # Re-request token and apply successful password reset
        auth_secure.request_password_reset(email)
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT reset_token FROM users WHERE username = ?", (username,))
            valid_token = cursor.fetchone()[0]

        # Execute with too short password
        success, msg = auth_secure.execute_password_reset_token(valid_token, "123")
        self.assertFalse(success)
        self.assertIn("at least 6 characters", msg.lower())

        # Execute with valid credentials
        success, msg = auth_secure.execute_password_reset_token(valid_token, new_password)
        self.assertTrue(success)
        self.assertIn("successfully reset", msg.lower())

        # Confirm we can log in with new password and old password fails
        success_old, _, _ = auth_secure.authenticate_secure_user(username, password)
        self.assertFalse(success_old)
        
        success_new, _, payload = auth_secure.authenticate_secure_user(username, new_password)
        self.assertTrue(success_new)
        self.assertEqual(payload["username"], username)

    def test_05_profile_management_center(self):
        """Assert profile fields update validation."""
        username = "profile_tester"
        
        auth_secure.register_secure_user(
            username=username, email="pt@test.com", password="password123", name="Profile Tester", workplace="None"
        )
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            uid = cursor.fetchone()[0]

        # Test update with empty name
        success, msg = auth_secure.update_user_profile(uid, "", "BOKU")
        self.assertFalse(success)
        self.assertIn("Full Name", msg)

        # Test successful update
        success, msg = auth_secure.update_user_profile(uid, "Updated Profile Name", "Vienna University of Natural Resources")
        self.assertTrue(success)
        
        # Confirm updates are in DB
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name, workplace FROM users WHERE id = ?", (uid,))
            name, workplace = cursor.fetchone()
            self.assertEqual(name, "Updated Profile Name")
            self.assertEqual(workplace, "Vienna University of Natural Resources")

    def test_06_security_logs_audit(self):
        """Assert security activities write audits containing usernames and details."""
        username = "audit_tester"
        auth_secure.register_secure_user(
            username=username, email="audit@test.com", password="password123", name="Audit Tester", workplace="BOKU"
        )
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            uid = cursor.fetchone()[0]
            
            # Check security_logs contains registration logs
            cursor.execute("SELECT action FROM security_logs WHERE user_id = ? ORDER BY timestamp DESC", (uid,))
            logs = [row[0] for row in cursor.fetchall()]
            self.assertTrue(any("registered" in log.lower() for log in logs))

if __name__ == "__main__":
    unittest.main()
