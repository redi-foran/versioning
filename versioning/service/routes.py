from .views import DeploymentView, ArtifactView


def setup_routes(app):
    DeploymentView.setup_routes(app)
    DeploymentCollectionView.setup_routes(app)
    ArtifactView.setup_routes(app)
