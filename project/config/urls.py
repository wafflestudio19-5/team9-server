
from django.contrib import admin
from django.urls import include, path

from django.conf import settings
from django.conf.urls.static import static

from rest_framework import permissions

from drf_yasg import openapi
from drf_yasg.views import get_schema_view


schema_view = get_schema_view(
    openapi.Info(
        title="Waffle Team-9 API",
        default_version="v1",
        description="Facebook toy project",
    ),
    url="http://3.34.188.255",
    public=True,
    permission_classes=(permissions.AllowAny,),
)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("user.urls")),
    path("api/v1/", include("newsfeed.urls")),
    path(
        "swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
]


# 미디어 파일을 위한 URL 지정
# urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
