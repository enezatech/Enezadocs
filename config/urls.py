from django.contrib import admin
from django.urls import include, path

from documentation.views import FaviconView, HomeView, SearchAllView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("docs/", include("documentation.urls")),
    path("search/", SearchAllView.as_view(), name="search"),
    path("favicon.ico", FaviconView.as_view(), name="favicon"),
    path("", HomeView.as_view(), name="home"),
]
