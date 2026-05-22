from django.contrib import admin
from django.urls import path
from api.views import home, multi_wdg_calculator

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home),
    path('api/multiWdgCalculator/', multi_wdg_calculator),
]
