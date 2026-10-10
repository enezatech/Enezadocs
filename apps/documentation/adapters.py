from allauth.account.adapter import DefaultAccountAdapter


class DocumentationAccountAdapter(DefaultAccountAdapter):
    """Gate new-account creation behind the site-wide registration switch.

    The social adapter delegates ``is_open_for_signup`` to this method, so
    returning False here blocks both email signup and first-time social
    signup while leaving existing users able to sign in.
    """

    def is_open_for_signup(self, request):
        from .models import HomePage

        return HomePage.load().allow_registration
