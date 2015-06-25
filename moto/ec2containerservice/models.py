from __future__ import unicode_literals

import boto.ec2containerservice
from moto.core import BaseBackend


class FakeService(object):

    def __init__(self, cluster, serviceName):
        self.cluster = cluster
        self.serviceName = serviceName
        self.taskDefinition = None
        self.desiredCount = 0
        self.serviceArn = "arn:aws:ecs:us-east-1:012345678910:service/{}".format(serviceName)

    def update(self, taskDefinition, desiredCount):
        self.taskDefinition = taskDefinition
        self.desiredCount = desiredCount

    def to_json(self):
        return {
            "clusterArn": self.cluster.clusterArn,
            "desiredCount": self.desiredCount,
            "loadBalancers": [],
            "deployments": [],
            "events": [],
            "runningCount": 0,
            "pendingCount": 0,
            "serviceName": self.serviceName,
            "serviceArn": self.serviceArn,
            "status": "ACTIVE",
            "taskDefintion": self.taskDefinition.arn
        }


class FakeCluster(object):

    def __init__(self, clusterName):
        self.activeServicesCount = 0
        self.clusterArn = "arn:aws:ecs:us-east-1:012345678910:cluster/{}".format(clusterName)
        self.clusterName = clusterName
        self.pendingTasksCount = 0
        self.registeredContainerInstancesCount = 0
        self.runningTasksCount = 0
        self.status = 'ACTIVE'
        self.services = []

    def create_service(self, serviceName, taskDefinition, desiredCount):
        service = FakeService(self, serviceName)
        service.update(taskDefinition, desiredCount)
        self.services.append(service)
        return service

    def to_json(self):
        return {
            "activeServicesCount": len(self.services),
            "clusterArn": self.clusterArn,
            "clusterName": self.clusterName,
            "pendingTasksCount": self.pendingTasksCount,
            "runningTasksCount": self.runningTasksCount,
            "registeredContainerInstancesCount": self.registeredContainerInstancesCount,
            "status": self.status
            }


class TaskDefinition(object):

    def __init__(self, family, containerDefinitions, volumes):
        self.family = family
        self.containerDefinitions = containerDefinitions
        self.volumes = volumes
        self.status = 'UNKNOWN'
        self.revision = '1'
        self.arn = "arn:aws:ecs:us-east-1:012345678910:task-definition/{}:{}".format(
            self.family, self.revision)

    def to_json(self):
        return {
            "containerDefinitions": self.containerDefinitions,
            "family": self.family,
            "revision": self.revision,
            "status": self.status,
            "taskDefinitionArn": self.arn,
            "volumes": self.volumes
        }


class EC2ContainerServiceBackend(BaseBackend):

    def __init__(self):
        self.clusters = []
        self.taskDefinitions = []

    def _get_cluster(self, name_or_arn):
        for cluster in self.clusters:
            if name_or_arn == cluster.clusterArn:
                return cluster
            if name_or_arn == cluster.clusterName:
                return cluster

    def _get_task_definition(self, name_or_arn):
        for taskDefinition in self.taskDefinitions:
            name = '{}:{}'.format(taskDefinition.family,
                                  taskDefinition.revision)
            print name
            if name == name_or_arn or name_or_arn == taskDefinition.arn:
                return taskDefinition
        raise Exception(name_or_arn)

    def create_cluster(self, cluster_name):
        cluster = FakeCluster(cluster_name)
        self.clusters.append(cluster)
        return cluster

    def register_task_definition(self, family, containerDefinitions, volumes):
        print "REGISTER"
        taskDefinition = TaskDefinition(family, containerDefinitions, volumes)
        self.taskDefinitions.append(taskDefinition)
        return taskDefinition

    def create_service(self, cluster, serviceName, taskDefinition, desiredCount):
        cluster = self._get_cluster(cluster)
        taskDefinition = self._get_task_definition(taskDefinition)
        return cluster.create_service(serviceName, taskDefinition, desiredCount)

    def list_services(self, cluster):
        cluster = self._get_cluster(cluster)
        serviceArns = [service.serviceArn for service in cluster.services]
        return serviceArns


ec2containerservice_backends = {}
for region in boto.ec2containerservice.regions():
    ec2containerservice_backends[region.name] = EC2ContainerServiceBackend()
