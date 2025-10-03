from django.urls import path
from .views import (
    sf_search_customers, sf_get_customer, sf_create_job,
    sf_oauth_test, sf_create_customer, platform_server, bluecollar_main_platform,home
)

urlpatterns = [
    path("", home, name="home"),
    path("home/", bluecollar_main_platform, name="bluecollar_main_platform_root"),

    # API JSON pour le front
    path("sf/customers/search", sf_search_customers, name="sf_search_customers"),
    path("sf/customers/<str:cid>", sf_get_customer, name="sf_get_customer"),
    path("sf/customers", sf_create_customer, name="sf_create_customer"),  # <-- AJOUTER CETTE LIGNE
    path("sf/jobs", sf_create_job, name="sf_create_job"),

    path("sf/oauth/test", sf_oauth_test, name="sf_oauth_test"),
    path("platform_server/", platform_server, name="platform_server"),
    path("bluecollar_main/", bluecollar_main_platform, name="bluecollar_main_platform"),
    
    
]