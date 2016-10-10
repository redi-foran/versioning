from sqlalchemy import *

metadata = MetaData()

image = Table('tImage', metadata,
        Column('ImageKey', Integer, primary_key=True),
        Column('Name', String(255), nullable=False, index=True))

artifact = Table('tArtifact', metadata,
        Column('ArtifactKey', Integer, primary_key=True),
        Column('Package', String(255), nullable=False),
        Column('Name', String(255), nullable=False),
        Index('idx_tArtifact_Package_Name', 'Package', 'Name', unique=True))

configuration = Table('tConfiguration', metadata,
        Column('ConfigurationKey', Integer, primary_key=True),
        Column('Repository', String(255), nullable=False, index=True))

version = Table('tVersion', metadata,
        Column('VersionKey', Integer, primary_key=True),
        Column('Environment', String(4), nullable=False),
        Column('DataCenter', String(3), nullable=False),
        # Does application really need to be 255? I think 4 (i.e. stream id) should work
        Column('Application', String(255), nullable=False),
        Column('Stripe', String(25), nullable=False),
        Column('Instance', String(25), nullable=False),
        Column('ImageKey', Integer, ForeignKey(image.c.ImageKey), nullable=False),
        Column('ImageVersion', String(255), nullable=False),
        Column('ArtifactKey', Integer, ForeignKey(artifact.c.ArtifactKey), nullable=False),
        Column('ArtifactVersion', String(255), nullable=False),
        Column('ConfigurationKey', Integer, ForeignKey(configuration.c.ConfigurationKey), nullable=False),
        Column('ConfigurationVersion', String(255), nullable=False),
        Column('IsActive', Boolean, default=True),
        Column('Username', String(16), nullable=False),
        Column('EffectiveUtc', BigInteger, nullable=False))


if __name__ == "__main__":
    engine = create_engine("sqlite:///foo.db")
    metadata.create_all(engine)
