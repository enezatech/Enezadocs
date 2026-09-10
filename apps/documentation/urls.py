from django.urls import path

from . import views

app_name = "documentation"

urlpatterns = [
    path("", views.SiteIndexView.as_view(), name="site_index"),
    path("<slug:slug>/", views.DocumentationView.as_view(), name="document"),
    path("<slug:slug>/search/", views.SearchView.as_view(), name="search"),
    path("<slug:slug>/assets/<path:path>/", views.AssetProxyView.as_view(), name="asset"),
    path("<slug:slug>/<path:path>/", views.DocumentationView.as_view(), name="document_path"),
]
