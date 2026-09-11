from .models import HomePage


def site_branding(request):
    return {"home": HomePage.load()}
