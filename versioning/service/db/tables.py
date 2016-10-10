from sqlalchemy import *
import datetime

metadata = MetaData()

image = Table('tImage', metadata,
        Column('image_key', Integer, primary_key=True),
        Column('name', String(255), nullable=False, index=True, unique=True))

artifactory = Table('tArtifactory', metadata,
        Column('artifactory_key', Integer, primary_key=True),
        Column('base_url', String(255), nullable=False, index=True, unique=True))

artifact = Table('tArtifact', metadata,
        Column('artifact_key', Integer, primary_key=True),
        Column('artifactory_key', Integer, ForeignKey(artifactory.c.artifactory_key), nullable=False),
        Column('package', String(255), nullable=False),
        Column('name', String(255), nullable=False),
        Index('idx_tArtifact_package_name', 'package', 'name', unique=True))

configuration = Table('tconfiguration_', metadata,
        Column('configuration_key', Integer, primary_key=True),
        Column('git_repository', String(255), nullable=False, index=True, unique=True))

version = Table('tVersion', metadata,
        Column('version_key', Integer, primary_key=True),
        Column('environment', String(4), nullable=False),
        Column('data_center', String(3), nullable=False),
        # Does application really need to be 255? I think 8 (i.e. stream id) should work
        Column('application', String(255), nullable=False),
        Column('stripe', String(25), nullable=False),
        Column('instance', String(25), nullable=False),
        Column('image_key', Integer, ForeignKey(image.c.image_key), nullable=False),
        Column('image_version', String(255), nullable=False),
        Column('artifact_key', Integer, ForeignKey(artifact.c.artifact_key), nullable=False),
        Column('artifact_version', String(255), nullable=False),
        Column('configuration_key', Integer, ForeignKey(configuration.c.configuration_key), nullable=False),
        Column('configuration_version', String(255), nullable=False),
        Column('is_active', Boolean, default=True),
        Column('username', String(16), nullable=False),
        Column('effective_utc', BigInteger, nullable=False),
        Column('deactivated_by', String(16), nullable=True),
        Column('deactivation_utc', BigInteger, nullable=True),
        Index('idx_tVersion_environment_data_center_application_stripe_instance', 'environment', 'data_center', 'application', 'stripe', 'instance', unique=False))
