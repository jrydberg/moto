from __future__ import unicode_literals
import json

from moto.core.responses import BaseResponse
from .models import ec2containerservice_backends


class EC2ContainerServiceResponse(BaseResponse):

    def param(self, name):
        data = json.loads(self.body)
        return data.get(name)

    @property
    def _backend(self):
        return ec2containerservice_backends[self.region]

    def respond(self, data):
        return json.dumps(data, indent=2)

    def create_cluster(self):
        cluster = self._backend.create_cluster(self.param('clusterName'))
        return self.respond({"cluster": cluster.to_json()})

    def list_container_instances(self):
        instances = self._backend.list_container_instances(self.param("cluster"))
        return self.respond({"containerInstanceArns": [
            instance.containerInstanceArn for instance in instances]})

    def describe_container_instances(self):
        failures, instances = self._backend.describe_container_instances(
            self.param("cluster"),
            self.param("containerInstances"))
        return self.respond({
            "failures": failures,
            "containerInstances": [instance.to_json() for instance in instances]
        })

    def register_task_definition(self):
        """
        Registers a new task definition from the supplied `family` and
        `containerDefinitions`.

        Optionally, you can add data volumes to your containers with the
        `volumes` parameter. For more information on task definition parameters
        and defaults, see Amazon ECS Task Definitions in the
        Amazon EC2 Container Service Developer Guide.
        """
        print repr(self.body)
        taskDefinition = self._backend.register_task_definition(
            self.param("family"), self.param("containerDefinitions"),
            self.param("volumes"))
        return self.respond({"taskDefinition": taskDefinition.to_json()})

    def list_services(self):
        serviceArns = self._backend.list_services(self.param("cluster"))
        return self.respond({"nextToken": None, "serviceArns": serviceArns})

    def create_service(self):
        service = self._backend.create_service(
            self.param("cluster"),
            self.param("serviceName"), self.param("taskDefinition"),
            self.param("desiredCount"))
        return self.respond({"service": service.to_json()})

    def update_service(self):
        service = self._backend.update_service(
            self.param("cluster"),
            self.param("service"),
            self.param("taskDefinition"),
            self.param("desiredCount"))
        return self.respond({"service": service.to_json()})

    def describe_services(self):
        failures, services = self._backend.describe_services(
            self.param("cluster"),
            self.param("services"))
        return self.respond({
            "failures": failures,
            "services": [service.to_json() for service in services]
        })

    def list_tasks(self):
        tasks = self._backend.list_tasks(
            self.param("cluster"), self.param("containerInstance"),
            self.param("desiredStatus"), self.param("family"),
            self.param("serviceName"))
        return self.respond({"taskArns": [task.taskArn for task in tasks]})

    def describe_tasks(self):
        failures, tasks = self._backend.describe_tasks(
            self.param("cluster"),
            self.param("tasks"))
        return self.respond({
            "failures": failures,
            "tasks": [task.to_json() for task in tasks]
        })
