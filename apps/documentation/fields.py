from __future__ import annotations

from django.db import models

from .services.crypto import decrypt_token, encrypt_token


class EncryptedTextField(models.TextField):
    """Text field whose value is encrypted at rest with a Fernet key.

    The in-memory value is always the plaintext: ``from_db_value`` decrypts on
    load and ``get_db_prep_value`` encrypts on save. Form inputs are plaintext
    and are encrypted only when written to the database.
    """

    def get_db_prep_value(self, value, connection, prepared=False):
        value = super().get_db_prep_value(value, connection, prepared)
        if value is None:
            return value
        return encrypt_token(value)

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return decrypt_token(value)

    def value_to_string(self, obj):
        value = self.value_from_object(obj)
        if value is None:
            return value
        return encrypt_token(value)
