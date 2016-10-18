from aiohttp import web
from sqlalchemy.orm import sessionmaker
from db import models
import datetime
import urllib.request
import json
from aiohttp_security import authorized_userid


#engine = create_engine("sqlite://")
#tables.metadata.create_all(engine)
#now = datetime.datetime.utcnow()
#engine.execute(tables.image.insert().values(name='rediforan/img-redi-centos'))
#engine.execute(tables.artifactory.insert().values(base_url='http://artifactory.rdti.com'))
#engine.execute(tables.artifact.insert().values(artifactory_key=1, package='com.redi.oms', name='legacyPublishing'))
#engine.execute(tables.configuration.insert().values(git_repository='git@github.com:redi-foran/config-historic-stream.git'))
#engine.execute(tables.version.insert().values(environment='dev', data_center='AM1', application='HTA1', stripe='sequencer', instance='primary',
    #image_key=1, image_version='latest', artifact_key=1, artifact_version='LATEST-SNAPSHOT', configuration_key=1, configuration_version='master', username='foran', effective_utc=now))


_DEPLOYMENT_ROUTE_NAME = 'deployment'
_ARTIFACT_ROUTE_NAME = 'artifact'


async def _deployment_to_dict(deployment, app):
    uri = app.router[_DEPLOYMENT_ROUTE_NAME].url(parts={
        'environment': deployment.environment,
        'data_center': deployment.data_center,
        'application': deployment.application,
        'stripe': deployment.stripe,
        'instance': deployment.instance
        })
    result = {'environment': deployment.environment,
            'data_center': deployment.data_center,
            'application': deployment.application,
            'stripe': deployment.stripe,
            'instance': deployment.instance,
            'image_name': deployment.image.name,
            'image_version': deployment.image_version,
            'artifact_group': deployment.artifact.group,
            'artifact_name': deployment.artifact.name,
            'artifact_version': deployment.artifact_version,
            'artifact_download_url': await deployment.get_artifact_download_url(app.loop),
            'git_repository': deployment.configuration.git_repository,
            'configuration_version': deployment.configuration_version,
            'effective_username': deployment.effective_username,
            'effective_utc': deployment.effective_utc,
            'is_active': deployment.is_active
            'uri': uri
            }
    if result['is_active']:
        result['deactivated_username'] = deployment.deactivated_username
        result['deactivated_utc'] = deployment.deactivated_utc
    return result


async def _artifact_to_dict(artifact, app):
    uri = app.router[_ARTIFACT_ROUTE_NAME].url(parts={
        'group': artifact.group,
        'name': artifact.name,
        'artifactory_base_uri': artifact.artifactory.base_uri
        })
    result = {'group': artifact.group,
            'name': artifact.name,
            'artifactory_base_uri': artifact.artifactory.base_uri,
            'effective_username': artifact.effective_username,
            'effective_utc': artifact.effective_utc,
            'is_active': artifact.is_active
            'uri': uri
            }
    if result['is_active']:
        result['deactivated_username'] = artifact.deactivated_username
        result['deactivated_utc'] = artifact.deactivated_utc
    return result


class ServiceBase(object):
    @property
    def loop(self):
        return self.request.app.loop

    def get_unit_of_work(self):
        return sessionmaker(bind=self.request.db_connection)


class DeploymentView(web.View, ServiceBase):
    @staticmethod
    def setup_routes(app, path_prefix=''):
        app.router.add_route('*', path_prefix + '/deployments/{environment}/{data_center}/{application}/{stripe}/{instance}', DeploymentView, name=_DEPLOYMENT_ROUTE_NAME)

    @property
    def _key(self):
        return {'environment': self.request.match_info.get('environment'),
                'data_center': self.request.match_info.get('data_center'),
                'application': self.request.match_info.get('application'),
                'stripe': self.request.match_info.get('stripe'),
                'instance': self.request.match_info.get('instance') }

    async def _get_image(self, name, unit_of_work):
        # TODO: Await on result
        return unit_of_work.query(models.Image).filter_by(name=name).one()

    async def _get_artifact(self, group, name, unit_of_work):
        # TODO: Await on result
        return unit_of_work.query(models.Artifact).filter_by(group=group, name=name).one()

    async def _get_configuration(self, git_repository, unit_of_work):
        # TODO: Await on result
        return unit_of_work.query(models.Configuration).filter_by(git_repository=git_repository).one()

    async def _get_deployment(self, unit_of_work):
        # TODO: Await on result
        return unit_of_work.query(models.Deployment).filter_by(**self._key, is_active=True).one()

    async def get(self):
        try:
            unit_of_work = self.get_unit_of_work()
            deployment = await self._get_deployment(unit_of_work)
            return web.json_response(await _deployment_to_dict(deployment, self.request.app), headers={'Last-Modified': deployment.effective_utc})
        except NoResultFound:
            return web.json_response(data=self._key, status=404)

    async def post(self):
        unit_of_work = self.get_unit_of_work()
        try:
            deployment = await self._get_deployment(unit_of_work)
            return web.json_response(self._key, status=405)
        except NoResultFound:
            pass
        username = await authorized_userid(self.request)
        data = await self.request.post()
        deployment = Deployment(environment=self.request.match_info.get('environment'),
                data_center=self.request.match_info.get('data_center'),
                application=self.request.match_info.get('application'),
                stripe=self.request.match_info.get('stripe'),
                instance=self.request.match_info.get('instance'),
                image=self._get_image(data['image_name'], unit_of_work),
                image_version=data['image_version'],
                artifact=self._get_artifact(data['artifact_group'], data['artifact_name'], unit_of_work),
                artifact_version=data['artifact_version'],
                configuration=self._get_configuration(data['git_repository'], unit_of_work),
                configuration_version=data['configuration_version'],
                effective_username=username)
        unit_of_work.add(deployment)
        unit_of_work.commit()
        return web.json_response(await _deployment_to_dict(deployment, self.request.app), status=201)

    async def delete(self):
        unit_of_work = self.get_unit_of_work()
        try:
            username = await authorized_userid(self.request)
            deployment = await self._get_deployment(unit_of_work)
            deployment.deactivate(username)
            unit_of_work.commit()
            return web.json_response({}, status=204)
        except NoResultFound:
            return web.json_response(self._key, status=404)

    async def patch(self):
        unit_of_work = self.get_unit_of_work()
        try:
            username = await authorized_userid(self.request)
            data = await self.request.post()
            image_version = data['image_version']
            artifact_version = data['artifact_version']
            configuration_version = data['configuration_version']
            timestamp = datetime.datetime.utcnow()
            old_deployment = await self._get_deployment(unit_of_work)
            if (old_deployment.image_version == image_version) and (old_deployment.artifact_version == artifact_version) and (old_deployment.configuration_version == configuration_version):
                return web.json_response(self._key, status=409)
            new_deployment = old_deployment.upgrade_to(image_version, artifact_version, configuration_version, username, datetime.datetime.utcnow())
            unit_of_work.add(new_deployment)
            unit_of_work.commit()
            return web.json_response(await _deployment_to_dict(new_deployment, self.loop), status=204)
        except NoResultFound:
            return web.json_response(self._key, status=404)


class ArtifactView(web.View, ServiceBase):
    @staticmethod
    def setup_routes(app, path_prefix=''):
        app.router.add_route('*', path_prefix + '/artifacts/{group}/{name}', ArtifactView, name=_ARTIFACT_ROUTE_NAME)

    async def _get_artifact(self, unit_of_work):
        return unit_of_work.query(models.Artifact).filter_by(**self._key).one()

    async def _get_artifactory(self, base_uri, username, utc_timestamp, unit_of_work):
        result = unit_of_work.query(models.Artifactory).filter_by(base_uri=base_uri).one_or_none()
        if result is None:
            result = Artifactory(base_uri=base_uri,
                    effective_username=username,
                    effective_utc=utc_timestamp)
            unit_of_work.add(result)
        return result

    @property
    def _key(self):
        return {'group': self.request.match_info.get('group'),
                'name': self.request.match_info.get('name') }

    async def get(self):
        try:
            unit_of_work = self.get_unit_of_work()
            artifact = await self._get_artifact(unit_of_work)
            return web.json_response(await _artifact_to_dict(deployment, self.request.app), headers={'Last-Modified': deployment.effective_utc})
        except NoResultFound:
            return web.json_response(data=self._key, status=404)

    async def post(self):
        unit_of_work = self.get_unit_of_work()
        try:
            deployment = await self._get_deployment(unit_of_work)
            return web.json_response(self._key, status=405)
        except NoResultFound:
            pass
        username = await authorized_userid(self.request)
        data = await self.request.post()
        utc_timestamp = datetime.datetime.utcnow()
        artifact = Artifact(**self._key,
                artifactory=await self._get_artifactory(data['base_uri'], username, utc_timestamp, unit_of_work),
                effective_username=username,
                effective_utc=utc_timestamp)
        unit_of_work.add(artifact)
        unit_of_work.commit()
        return web.json_response(await _artifact_to_dict(artifact, self.request.app), status=201)

    async def put(self):
        unit_of_work = self.get_unit_of_work()
        try:
            username = await authorized_userid(self.request)
            data = await self.request.post()
            utc_timestamp = datetime.datetime.utcnow()
            artifact = await self._get_artifact(unit_of_work)
            artifactory = await self._get_artifactory(data['base_uri'], username, utc_timestamp, unit_of_work)
            (new_artifact, new_deployments) = artifact.change_to_artifactory(artifactory, session['username'], utc_timestamp, unit_of_work)
            unit_of_work.add(new_artifact)
            for deployment in new_deployments:
                unit_of_work.add(new_deployment)
            unit_of_work.commit()
            return web.json_response({}, status=204)
        except NoResultFound:
            return web.json_response(self._key, status=404)

    async def delete(self):
        unit_of_work = self.get_unit_of_work()
        try:
            username = await authorized_userid(self.request)
            artifact = await self._get_artifact(unit_of_work)
            artifact.deactivate(username)
            unit_of_work.commit()
            return web.json_response({}, status=204)
        except NoResultFound:
            return web.json_response(self._key, status=404)


def _set_if_present(source_key, source, destination, destination_key=None):
    if destination_key is None:
        destination_key = source_key
    if source_key in source:
        destination[destination_key] = source[source_key]


class DeploymentCollectionView(web.View, ServiceBase):
    @staticmethod
    def setup_routes(app, path_prefix=''):
        app.router.add_route('*', path_prefix + '/deployments', DeploymentCollectionView)

    async def get(self):
        lookup = {}
        for parameter in ['is_active', 'environment', 'data_center', 'application', 'stripe', 'instance']:
            _set_if_present(parameter, self.request.rel_url.query, lookup)
        unit_of_work = self.get_unit_of_work()
        deployments = []
        latest_utc = 0
        for deployment in self._get_deployments(unit_of_work, **lookup):
            deployments.append(await _deployment_to_dict(deployment, self.loop))
            if deployment.effective_utc > latest_utc:
                latest_utc = deployment.effective_utc
        return web.json_response(deployments, headers={'Last-Modified': latest_utc})

    async def _get_deployments(self, unit_of_work, **parameters):
        return unit_of_work.query(models.Deployment).filter_by(**parameters)
