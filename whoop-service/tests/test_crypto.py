from core.crypto import decrypt_token, encrypt_token

_KEY = "q1D3_xXbvnPRBJsZmexB22Gr9Fiqkwb74KQlwsDNaEA="  # a real, valid Fernet key


class TestCrypto:
    def test_happy_path_round_trips(self):
        assert decrypt_token(encrypt_token("a-real-whoop-token", _KEY), _KEY) == (
            "a-real-whoop-token"
        )

    def test_edge_case_the_same_plaintext_produces_different_ciphertext_each_time(self):
        """Scope: Fernet includes a random IV per encryption — two
        encryptions of the identical token must never be byte-identical.
        A stored ciphertext leaking wouldn't reveal whether it matches
        another user's token by comparing ciphertext alone."""
        first = encrypt_token("same-token", _KEY)
        second = encrypt_token("same-token", _KEY)

        assert first != second
        assert decrypt_token(first, _KEY) == decrypt_token(second, _KEY) == "same-token"
