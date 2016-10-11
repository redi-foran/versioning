from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, BigInteger, ForeignKey, Index, Table, Boolean, String
from sqlalchemy.orm import relationship
from aiohttp import ClientSession
from datetime import datetime


Base = declarative_base()


class Auditable(object):
    effective_username = Column(String(16), nullable=False)
    effective_utc = Column(BigInteger, nullable=False, default=datetime.utcnow)

    def clone(self):
        clone = __class__()
        self._build_clone(clone)
        return clone

    def _build_clone(self, clone):
        clone.effective_username = self.effective_username
        clone.effective_utc = self.effective_utc


class Deactivatable(Auditable):
    deactivated_username = Column(String(16), nullable=False)
    deactivated_utc = Column(BigInteger, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)

    def deactivate(self, username, utc_timestamp=datetime.utcnow()):
        if self.is_active:
            self.deactivated_username = username
            self.deactivated_utc = utc_timestamp
            self.is_active = False

    def activate(self, username, utc_timestamp=datetime.utcnow()):
        effective_username = username
        effective_utc = utc_timestamp
        self.is_active = True

    def _build_clone(self, clone):
        clone.deactivated_username = self.deactivated_username
        clone.deactivated_utc = self.deactivated_utc
        clone.is_active = self.is_active
        super(self, Deactivatable).build_clone(clone)


class Image(Base, Auditable):
    __tablename__ = 'tImage'

    image_key = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, index=True, unique=True)

    def _build_clone(self, clone):
        clone.name = self.name
        super(self, Image).build_clone(clone)


class Artifactory(Base, Deactivatable):
    __tablename__ = 'tArtifactory'

    artifactory_key = Column(Integer, primary_key=True)
    base_uri = Column(String(255), nullable=False, index=True, unique=True)

    def _build_clone(self, clone):
        clone.base_uri = self.base_uri
        super(self, Artifactory).build_clone(clone)


class Artifact(Base, Deactivatable):
    __tablename__ = 'tArtifact'

    artifact_key = Column(Integer, primary_key=True)
    artifactory_key = Column(Integer, ForeignKey(Artifactory.__table__.c.artifactory_key), nullable=False)
    artifactory = relationship("Artifactory", back_populates='artifacts')
    group = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)

    def _build_clone(self, clone):
        clone.artifactory = self.artifactory
        clone.group = self.group
        clone.name = self.name
        super(self, Artifact).build_clone(clone)

    async def get_uri(self, version, loop):
        result = None
        async with ClientSession(loop=loop) as session:
            package_uri = ''
            async with session.get('%s/artifactory/api/search/gavc' % self.artifactory.base_uri,
                    params={'g': self.group, 'a': self.name, 'v': version, 'c': 'release'}) as response:
                json_result = await response.json()['results']
                if json_result:
                    package_uri = json_result[0]['uri']
            if package_uri:
                async with session.get(package_uri) as response:
                    result = await response.json()['downloadUri']
        return result

    def change_to_artifactory(self, artifactory, username, utc_timestamp):
        new_artifact = Artifact(group=self.group,
            name=self.name,
            artifactory=artifactory,
            effective_username=username,
            effective_utc=utc_timestamp)
        new_deployments = []
        for deployment in self.deployments:
            if deployment.is_active:
                new_deployments.append(deployment.switch_to_artifact(new_artifact, username, utc_timestamp))
        self.deactivate(username, utc_timestamp)
        return (new_artifact, new_deployments)

    def deactivate(self, username, utc_timestamp=datetime.utcnow()):
        for deployment in self.deployments:
            deployment.deactivate(username, utc_timestamp)
        super(self, Artifact).deactivate(username, utc_timestamp)


class Configuration(Base, Auditable):
    __tablename__ = 'tConfiguration'

    configuration_key = Column(Integer, primary_key=True)
    git_repository = Column(String(255), nullable=False, index=True, unique=True)

    def _build_clone(self, clone):
        clone.git_repository = self.git_repository
        super(self, Configuration).build_clone(clone)


class Deployment(Base, Deactivatable):
    __tablename__ = 'tDeployment'

    deployment_key = Column(Integer, primary_key=True)
    environment = Column(String(4), nullable=False)
    data_center = Column(String(3), nullable=False)
    # Does application really need to be 255? I think 8 (i.e. stream id) should work
    application = Column(String(255), nullable=False)
    stripe = Column(String(25), nullable=False)
    instance = Column(String(25), nullable=False)
    image_key = Column(Integer, ForeignKey(Image.__table__.c.image_key), nullable=False)
    image_version = Column(String(255), nullable=False)
    image = relationship("Image", back_populates='deployments')
    artifact_key = Column(Integer, ForeignKey(Artifact.__table__.c.artifact_key), nullable=False)
    artifact_version = Column(String(255), nullable=False)
    artifact = relationship("Artifact", back_populates='deployments')
    configuration_key = Column(Integer, ForeignKey(Configuration.__table__.c.configuration_key), nullable=False)
    configuration_version = Column(String(255), nullable=False)
    configuration = relationship("Configuration", back_populates='deployments')

    def _build_clone(self, clone):
        clone.environment = self.environment
        clone.data_center = self.data_center
        clone.application = self.application
        clone.stripe = self.stripe
        clone.instance = self.instance
        clone.image = self.image
        clone.image_version = self.image_version
        clone.artifact = self.artifact
        clone.artifact_version = self.artifact_version
        clone.configuration = self.configuration
        clone.configuration_version = self.configuration_version
        super(self, Deployment).build_clone(clone)

    async def get_artifact_uri(self, loop):
        return await self.artifact.get_uri(self.artifact_version, loop)

    def upgrade_to(self, image_version, artifact_version, configuration_version, username, utc_timestamp):
        self.deactivate(username, utc_timestamp)
        upgraded_deployment = self.clone()
        if self.image_version != image_version:
            upgraded_deployment.image_version = image_version
        if self.artifact_version != artifact_version:
            upgraded_deployment.artifact_version = artifact_version
        if self.configuration_version != configuration_version:
            upgraded_deployment.configuration_version = configuration_version
        upgraded_deployment.activate(username, utc_timestamp)
        return upgraded_deployment

    def switch_to_image(self, image, username, utc_timestamp):
        switched_deployment = self.clone()
        switched_deployment.image = image
        switched_deployment.activate(username, utc_timestamp)
        return switched_deployment

    def switch_to_artifact(self, artifact, username, utc_timestamp):
        switched_deployment = self.clone()
        switched_deployment.artifact = artifact
        switched_deployment.activate(username, utc_timestamp)
        return switched_deployment

    def switch_to_configuration(self, configuration, username, utc_timestamp):
        switched_deployment = self.clone()
        switched_deployment.configuration = configuration
        switched_deployment.activate(username, utc_timestamp)
        return switched_deployment


artifact_index = Index('idx_tArtifact_group_name', Artifact.__table__.c.group, Artifact.__table__.c.name, unique=False)
artifact_index = Index('idx_tArtifact_group_name_artifactory', Artifact.__table__.c.group, Artifact.__table__.c.name, Artifact.__table__.c.artifactory_key, unique=True)
deployment_index = Index('idx_tDeployment_env_dc_app_s_i', 'environment', 'data_center', 'application', 'stripe', 'instance', unique=False)
