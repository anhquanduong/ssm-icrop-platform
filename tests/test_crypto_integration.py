import os
import sys
import tempfile
import unittest
import json
import sqlite3

# Add 'app' directory to Python system path to resolve imports properly
workspace_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
app_dir = os.path.join(workspace_dir, "app")
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from utils.db_manager import DatabaseManager
from utils.crypto_vault import CropCryptoVault, SecurityError

class TestCropCryptoIntegration(unittest.TestCase):
    def setUp(self):
        # Create a temporary database for testing to ensure isolated tests
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        self.db = DatabaseManager(db_path=self.temp_db_path)
        
        # Test values
        self.user_password_hash = "60e1d1f054baec2fb2ab97ebc9735d4d$49090b8ffbe3ecff9a689bcfbd06e2373300300a84e27f677fb28b49527ecb8f"
        self.user_salt = "60e1d1f054baec2fb2ab97ebc9735d4d"
        self.plain_json = json.dumps({
            "CROP": "Maize",
            "TBD": 8.0,
            "RUE_MAX": 3.5,
            "IRUE": 3.5,
            "SLA": 0.022
        })
        
        # Derive key
        self.session_key = CropCryptoVault.generate_key_from_user_session(
            self.user_password_hash, self.user_salt
        )
        
        # Insert a mock user to satisfy the foreign key constraint
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (id, username, password_hash) VALUES (1, 'test_user', ?)",
                (self.user_password_hash,)
            )
            conn.commit()

    def tearDown(self):
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
                print(f"Teardown clean-up warning: {teardown_err}")

    def test_01_key_derivation_vault(self):
        """Assert that PBKDF2 derived Fernet keys are base64 URL-safe, stable, and unique."""
        # Key should be a non-empty string
        self.assertTrue(isinstance(self.session_key, str))
        self.assertTrue(len(self.session_key) > 0)
        
        # Stability: Key derived from the same inputs must match exactly
        key_2 = CropCryptoVault.generate_key_from_user_session(
            self.user_password_hash, self.user_salt
        )
        self.assertEqual(self.session_key, key_2)
        
        # Uniqueness: Key derived from a different password or salt must not match
        different_key = CropCryptoVault.generate_key_from_user_session(
            self.user_password_hash, "different_salt_12345"
        )
        self.assertNotEqual(self.session_key, different_key)

    def test_02_encryption_decryption_vault(self):
        """Assert symmetric encryption/decryption round-trip and validation on failure."""
        cipher_bytes = CropCryptoVault.encrypt_parameters(self.plain_json, self.session_key)
        self.assertTrue(isinstance(cipher_bytes, bytes))
        self.assertTrue(len(cipher_bytes) > 0)
        
        # Decryption success
        decrypted_str = CropCryptoVault.decrypt_parameters(cipher_bytes, self.session_key)
        self.assertEqual(self.plain_json, decrypted_str)
        
        # Decryption failure on corrupted key
        bad_key = CropCryptoVault.generate_key_from_user_session(
            self.user_password_hash, "different_salt_12345"
        )
        with self.assertRaises(SecurityError):
            CropCryptoVault.decrypt_parameters(cipher_bytes, bad_key)

    def test_03_db_hook_transparent_saving_and_routing(self):
        """Assert saving public parameters as plain JSON and private parameters as AES ciphertext."""
        user_id = 1
        crop_name_pub = "Maize Hybrid Public"
        crop_name_priv = "Maize Hybrid Private"
        param_dict = json.loads(self.plain_json)
        
        # 1. Save Public crop profile (should be plain JSON)
        pub_id = self.db.save_crop_profile(
            user_id=user_id,
            crop_name=crop_name_pub,
            is_public=1,
            param_dict=param_dict
        )
        self.assertTrue(pub_id > 0)
        
        # Verify in raw database directly that public profile parameters_json is plain JSON
        with sqlite3.connect(self.temp_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT parameters_json FROM crop_profiles WHERE id = ?", (pub_id,))
            raw_payload = cursor.fetchone()[0]
            # Try to load as json to verify it is valid plain text json
            parsed = json.loads(raw_payload)
            self.assertEqual(parsed["CROP"], "Maize")
            self.assertEqual(parsed["TBD"], 8.0)
            
        # 2. Save Private crop profile (should be encrypted)
        priv_id = self.db.save_crop_profile(
            user_id=user_id,
            crop_name=crop_name_priv,
            is_public=0,
            param_dict=param_dict,
            session_key=self.session_key
        )
        self.assertTrue(priv_id > 0)
        
        # Verify in raw database directly that private profile is encrypted (NOT plain text JSON)
        with sqlite3.connect(self.temp_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT parameters_json FROM crop_profiles WHERE id = ?", (priv_id,))
            raw_payload = cursor.fetchone()[0]
            # Should NOT be plain JSON
            with self.assertRaises(ValueError):
                json.loads(raw_payload)
            
            # Encrypted payload should be decryptable back to our parameters
            decrypted = CropCryptoVault.decrypt_parameters(raw_payload.encode('utf-8'), self.session_key)
            parsed = json.loads(decrypted)
            self.assertEqual(parsed["CROP"], "Maize")
            
        # 3. Save Private without session key should raise ValueError
        with self.assertRaises(ValueError):
            self.db.save_crop_profile(
                user_id=user_id,
                crop_name="Failed Private",
                is_public=0,
                param_dict=param_dict,
                session_key=None
            )

    def test_04_transparent_decryption_routing_on_fetch(self):
        """Assert transparent on-the-fly decryption or exception raising on missing/invalid keys."""
        user_id = 1
        param_dict = json.loads(self.plain_json)
        
        # Save one public and one private profile
        self.db.save_crop_profile(
            user_id=user_id,
            crop_name="Maize Public",
            is_public=1,
            param_dict=param_dict
        )
        
        self.db.save_crop_profile(
            user_id=user_id,
            crop_name="Maize Private",
            is_public=0,
            param_dict=param_dict,
            session_key=self.session_key
        )
        
        # Fetching with correct key should return BOTH profiles decrypted in memory
        profiles = self.db.get_available_profiles(current_user_id=user_id, session_key=self.session_key)
        self.assertEqual(len(profiles), 2)
        
        # Check both are valid dictionaries
        names = [p["crop_name"] for p in profiles]
        self.assertIn("Maize Public", names)
        self.assertIn("Maize Private", names)
        
        for p in profiles:
            self.assertTrue(isinstance(p["parameters"], dict))
            self.assertEqual(p["parameters"]["CROP"], "Maize")
            
        # Fetching with NO key should raise PermissionError (strict security block)
        with self.assertRaises(PermissionError):
            self.db.get_available_profiles(current_user_id=user_id, session_key=None)
            
        # Fetching with WRONG key should raise PermissionError (strict security block)
        wrong_key = CropCryptoVault.generate_key_from_user_session(
            self.user_password_hash, "different_salt_12345"
        )
        with self.assertRaises(PermissionError):
            self.db.get_available_profiles(current_user_id=user_id, session_key=wrong_key)

if __name__ == "__main__":
    unittest.main()
