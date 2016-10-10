from aiohttp import web
from sqlalchemy import create_engine, select, and_
from sqlalchemy.sql import bindparam
from sqlalchemy.sql.expression import label
from db import tables
import datetime
import urllib.request
import json


get_version_statement = select([tables.version.c.version_key,
    tables.version.c.environment, tables.version.c.data_center, tables.version.c.application, tables.version.c.stripe, tables.version.c.instance,
    tables.version.c.image_key, label('image_name', tables.image.c.name), tables.version.c.image_version,
    tables.version.c.artifact_key, label('artifactory_base_url', tables.artifactory.c.base_url), label('artifact_package', tables.artifact.c.package), label('artifact_name', tables.artifact.c.name), tables.version.c.artifact_version,
    tables.version.c.configuration_key, tables.configuration.c.git_repository, tables.version.c.configuration_version,
    tables.version.c.username, tables.version.c.effective_utc, tables.version.c.deactivated_by, tables.version.c.deactivation_utc]).\
            select_from(tables.version.join(tables.image).join(tables.artifact).join(tables.configuration).join(tables.artifactory)).\
            where(and_(
                tables.version.c.environment == bindparam('b_environment'),
                tables.version.c.data_center == bindparam('b_data_center'),
                tables.version.c.application == bindparam('b_application'),
                tables.version.c.stripe == bindparam('b_stripe'),
                tables.version.c.instance == bindparam('b_instance'),
                tables.version.c.is_active == True))

activate_version_statement = tables.version.insert().values(
        environment = bindparam('b_environment'),
        data_center = bindparam('b_data_center'),
        application = bindparam('b_application'),
        stripe = bindparam('b_stripe'),
        instance = bindparam('b_instance'),
        image_key = bindparam('b_image_key'),
        image_version = bindparam('b_image_version'),
        artifact_key = bindparam('b_artifact_key'),
        artifact_version = bindparam('b_artifact_version'),
        configuration_key = bindparam('b_configuration_key'),
        configuration_version = bindparam('b_configuration_version'),
        username = bindparam('b_username'),
        effective_utc = bindparam('b_effective_utc'))

deactivate_version_statement = tables.version.update().\
        where(and_(
                tables.version.c.environment == bindparam('b_environment'),
                tables.version.c.data_center == bindparam('b_data_center'),
                tables.version.c.application == bindparam('b_application'),
                tables.version.c.stripe == bindparam('b_stripe'),
                tables.version.c.instance == bindparam('b_instance'),
                tables.version.c.is_active == True)).\
        values(
                deactivated_by = bindparam('b_deactivated_by'),
                deactivation_utc = bindparam('b_deactivation_utc'),
                is_active = False)


#engine = create_engine("sqlite://")
#tables.metadata.create_all(engine)
#now = datetime.datetime.utcnow()
#engine.execute(tables.image.insert().values(name='rediforan/img-redi-centos'))
#engine.execute(tables.artifactory.insert().values(base_url='http://artifactory.rdti.com'))
#engine.execute(tables.artifact.insert().values(artifactory_key=1, package='com.redi.oms', name='legacyPublishing'))
#engine.execute(tables.configuration.insert().values(git_repository='git@github.com:redi-foran/config-historic-stream.git'))
#engine.execute(tables.version.insert().values(environment='dev', data_center='AM1', application='HTA1', stripe='sequencer', instance='primary',
    #image_key=1, image_version='latest', artifact_key=1, artifact_version='LATEST-SNAPSHOT', configuration_key=1, configuration_version='master', username='foran', effective_utc=now))


class VersionView(web.View):
    def __init__(self, *args, **kwargs):
        self._current = None
        self._connection = None
        super(VersionView, self).__init__(*args, **kwargs)

    @staticmethod
    def setup_routes(app, path_prefix=''):
        app.router.add_route('*', path_prefix + '/versions/{environment}/{data_center}/{application}/{stripe}/{instance}.{format}', VersionView)

    @property
    def engine(self):
        return self.request.db_engine

    @property
    def connection(self):
        return self.request.db_connection

    @property
    def _key(self):
        return { 'b_environment': self.request.match_info.get('environment'),
                'b_data_center': self.request.match_info.get('data_center'),
                'b_application': self.request.match_info.get('application'),
                'b_stripe': self.request.match_info.get('stripe'),
                'b_instance': self.request.match_info.get('instance') }

    def _get_image_key(self, name):
        result = self.connection.execute(select([tables.image.c.image_key]).where(tables.image.c.name == name)).fetchone()
        if result is None:
            return self.connection.execute(tables.image.insert().values(name=name)).inserted_primary_key[0]
        return result['image_key']

    def _get_artifact_key(self, package, name):
        result = self.connection.execute(select([tables.artifact.c.artifact_key]).where(and_(
            tables.artifact.c.package == package,
            tables.artifact.c.name == name))).fetchone()
        if result is None:
            return self.connection.execute(tables.artifact.insert().values(package=package, name=name)).inserted_primary_key[0]
        return result['artifact_key']

    def _get_configuration_key(self, git_repository):
        result = self.connection.execute(select([tables.configuration.c.configuration_key]).where(tables.configuration.c.git_repository == git_repository)).fetchone()
        if result is None:
            return self.connection.execute(tables.configuration.insert().values(git_repository=git_repository)).inserted_primary_key[0]
        return result['configuration_key']

    @property
    def current(self):
        if self._current is None:
            self._current = self.connection.execute(get_version_statement, **self._key).fetchone()
        return self._current

    def get_artifact_uri(self):
        result = None
        if self.current is not None:
            artifactory_query_url = '%s/artifactory/api/search/gavc?c=release' % self.current['artifactory_base_url']
            artifactory_query_url += '&g=%s' % self.current['artifact_package']
            artifactory_query_url += '&a=%s' % self.current['artifact_name']
            artifactory_query_url += '&v=%s' % self.current['artifact_version']
            package_url = ''
            with urllib.request.urlopen(artifactory_query_url) as response:
                json_result = json.loads(response.read().decode('utf-8'))['results']
                if json_result:
                    package_url = json_result[0]['uri']
            if package_url:
                with urllib.request.urlopen(package_url) as response:
                    json_result = json.loads(response.read().decode('utf-8'))
                    print(str(json_result))
                    result = json_result['downloadUri']
        return result

    @property
    def current_as_dict(self):
        if self.current is None:
            return {}
        return {'environment': self.current['environment'],
                'data_center': self.current['data_center'],
                'application': self.current['application'],
                'stripe': self.current['stripe'],
                'instance': self.current['instance'],
                'image_name': self.current['image_name'],
                'image_version': self.current['image_version'],
                'artifact_package': self.current['artifact_package'],
                'artifact_name': self.current['artifact_name'],
                'artifact_version': self.current['artifact_version'],
                'artifact_uri': self.get_artifact_uri(),
                'git_repository': self.current['git_repository'],
                'configuration_version': self.current['configuration_version'],
                'username': self.current['username'],
                'effective_utc': self.current['effective_utc'] }


    async def get(self):
        format = self.request.match_info.get('format')
        if format != 'json':
            raise TypeError("Only json is supported")
        if self.current is None:
            return web.json_response(self._key, status=404)
        return web.json_response(self.current_as_dict, headers={'Last-Modified': self.current['effective_utc']})


    async def post(self):
        with self.connection.begin():
            if self.current is not None:
                return web.json_response(self._key, status=405)
            data = await self.request.post()
            self._activate(data['username'],
                    self._get_image_key(data['image_name']), data['image_version'],
                    self._get_artifact_key(data['artifact_package'], data['artifact_name']), data['artifact_version'],
                    self._get_configuration_key(data['git_repository']), data['configuration_version'],
                    datetime.datetime.utcnow())
            return web.json_response(self.current_as_dict, status=201)

    def _activate(self, username, image_key, image_version, artifact_key, artifact_version, configuration_key, configuration_version, timestamp):
        return self.connection.execute(activate_version_statement, **self._key, b_username=username,
                b_image_key=image_key, b_image_version=image_version,
                b_artifact_key=artifact_key, b_artifact_version=artifact_version,
                b_configuration_key=configuration_key, b_configuration_version=configuration_version,
                b_effective_utc=timestamp)

    def _deactivate(self, username, timestamp):
        # Do we care about when something was deactivated (and/or who deactivated it)?
        result = self.connection.execute(deactivate_version_statement, **self._key, b_deactivated_by=username, b_deactivation_utc=timestamp)
        self._current = None
        return result


    async def delete(self):
        with self.connection.begin():
            if self.current is None:
                return web.json_response(self._key, status=404)
            self._deactivate(datetime.datetime.utcnow())
            return web.json_response({}, status=204)


    async def patch(self):
        with self.connection.begin():
            if self.current is None:
                return web.json_response(self._key, status=404)
            previous = self.current
            data = await self.request.post()
            timestamp = datetime.datetime.utcnow()
            self._deactivate(data['username'], timestamp)
            self._activate(self.request.POST['username'],
                previous['image_key'], data.get('image_version', previous['image_version']),
                previous['artifact_key'], data.get('artifact_version', previous['artifact_version']),
                previous['configuration_key'], data.get('configuration_version', previous['configuration_version']),
                timestamp)
            return web.json_response(self.current_as_dict, status=200)
