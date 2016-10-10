from .views import VersionView


def setup_routes(app):
    VersionView.setup_routes(app)
