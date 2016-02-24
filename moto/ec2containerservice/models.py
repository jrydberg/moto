from __future__ import unicode_literals

import uuid
import time

import boto.ec2containerservice
from moto.core import BaseBackend


class _Container(object):
    """A Docker container that is part of a task."""

    def __init__(self, task, name):
        self.task = task
        self.name = name
        self.lastStatus = 'RUNNING'
        self.reason = None
        self.exitCode = None
        self.containerArn = "arn:aws:ecs:us-east-1:012345678910:container/{}".format(str(uuid.uuid4()))

    def to_json(self):
        result = {
            "containerArn": self.containerArn,
            "lastStatus": self.lastStatus,
            "name": self.name,
            "taskArn": self.task.taskArn,
            "networkBindings": []
        }
        if self.reason is not None:
            result["reason"] = self.reason
        if self.exitCode is not None:
            result["exitCode"] = self.exitCode
        return result

    def stop(self, exitCode):
        self.exitCode = exitCode
        self.lastStatus = 'STOPPED'

    def fail(self, reason):
        self.lastStatus = 'STOPPED'
        self.reason = reason


class FakeTask(object):

    def __init__(self, cluster, taskDefinition, service, startedBy, overrides):
        self.cluster = cluster
        self.taskDefinition = taskDefinition
        self.lastStatus = 'PENDING'
        self.desiredStatus = 'RUNNING'
        self.taskArn = "arn:aws:ecs:us-east-1:012345678910:task/{}".format(str(uuid.uuid4()))
        self.service = service
        self.startedBy = startedBy
        self.overrides = overrides
        self.containerInstance = None
        self.createdAt = time.time()
        self.startedAt = None
        self.stoppedAt = None
        self.containers = []

    def to_json(self):
        result = {
            "clusterArn": self.cluster.clusterArn,
            "containers": [c.to_json() for c in self.containers],
            "desiredStatus": self.desiredStatus,
            "lastStatus": self.lastStatus,
            "overrides": self.overrides,
            "taskArn": self.taskArn,
            "taskDefinitionArn": self.taskDefinition.arn,
            "startedBy": self.startedBy,
        }
        for timestamp in ("createdAt", "startedAt", "stoppedAt"):
            if getattr(self, timestamp):
                result[timestamp] = getattr(self, timestamp)
        if self.containerInstance:
            result['containerInstanceArn'] = self.containerInstance.containerInstanceArn
        return result

    def assign(self, containerInstance):
        self.lastStatus = 'RUNNING'
        self.startedAt = time.time()
        self.containerInstance = containerInstance
        self.containerInstance.tasks.append(self)
        for containerDef in self.taskDefinition.containerDefinitions:
            self.containers.append(_Container(self, containerDef.get('name')))


class Deployment(object):

    def __init__(self, service, taskDefinition, desiredCount):
        self.service = service
        self.taskDefinition = taskDefinition
        self.desired_count = desiredCount
        self.created_at = 1432829320.611
        self.updated_at = 1432829320.611
        self.id = "ecs-svc/" + str(uuid.uuid4())
        self.pending_count = 0
        self.running_count = 0
        self.status = "PRIMARY"

    def to_json(self):
        tasks = self.service.cluster.list_tasks(
            None, None, None, self.service.serviceName, self.id)
        running_count = len([t for t in tasks if t.lastStatus == 'RUNNING'])
        pending_count = len([t for t in tasks if t.lastStatus == 'PENDING'])

        return {
            "createdAt": self.created_at,
            "desiredCount": self.desired_count,
            "id": self.id,
            "pendingCount": pending_count,
            "runningCount": running_count,
            "status": self.status,
            "taskDefinition": self.taskDefinition.arn,
            "updatedAt": self.updated_at,
        }


class FakeService(object):

    def __init__(self, cluster, serviceName):
        self.cluster = cluster
        self.serviceName = serviceName
        self.taskDefinition = None
        self.desiredCount = 0
        self.serviceArn = "arn:aws:ecs:us-east-1:012345678910:service/{}".format(serviceName)
        self.deployments = []
        self.events = []

    def emit(self, message):
        self.events.insert(0, {
            "createdAt": time.time(),
            "message": "(service {}) {}".format(self.serviceName, message),
            "id": str(uuid.uuid4())
        })

    def _new_deployment(self, taskDefinition, desiredCount):
        new_deployment = Deployment(self, taskDefinition, desiredCount)
        if self.deployments:
            current_deployment = self.deployments[-1]
            self.shut_down_deployment(current_deployment)
        self.deployments.append(new_deployment)

    def shut_down_deployment(self, deployment):
        tasks = self.cluster.list_tasks(
            None, None, None, self.serviceName, deployment.id)
        for task in tasks:
            task.desiredStatus = task.lastStatus = 'STOPPED'
            task.stoppedAt = time.time()
        deployment.status = 'INACTIVE'

    @property
    def _tasks(self):
        return self.cluster.list_tasks(
            None, None, None, self.serviceName, deployment.id)

    def ensure_desired_count(self, deployment):
        tasks = self.cluster.list_tasks(
            None, None, None, self.serviceName, deployment.id)
        count = deployment.desired_count - len(tasks)
        if count > 0:
            self.cluster.run_tasks(
                count, {}, deployment.id, self.taskDefinition, self)
        elif count < 0:
            while count < 0:
                task = tasks.pop(0)
                task.desiredStatus = task.lastStatus = 'STOPPED'
                task.stoppedAt = time.time()
                count += 1
        # check if we have reached steady state
        tasks = self.cluster.list_tasks(
            None, None, None, self.serviceName, deployment.id)
        count = deployment.desired_count - len(tasks)
        if count == 0:
            self.emit("has reached a steady state.")

    def update(self, taskDefinition, desiredCount):
        if taskDefinition is not None:
            if taskDefinition != self.taskDefinition:
                self._new_deployment(taskDefinition, desiredCount or self.desiredCount)
            self.taskDefinition = taskDefinition
        if desiredCount is not None:
            self.desiredCount = desiredCount
            self.deployments[-1].desired_count = desiredCount

        print "UPDATED", self.taskDefinition, self.desiredCount
        self.ensure_desired_count(self.deployments[-1])

    def to_json(self):
        # make sure we have enough running or not running tasks
        tasks = self.cluster.list_tasks(None, None, None, self.serviceName)
        running_count = len([t for t in tasks if t.lastStatus == 'RUNNING'])
        pending_count = len([t for t in tasks if t.lastStatus == 'PENDING'])

        return {
            "clusterArn": self.cluster.clusterArn,
            "desiredCount": self.desiredCount,
            "loadBalancers": [],
            "deployments": [d.to_json() for d in self.deployments],
            "events": self.events,
            "runningCount": running_count,
            "pendingCount": pending_count,
            "serviceName": self.serviceName,
            "serviceArn": self.serviceArn,
            "status": "ACTIVE",
            "taskDefinition": self.taskDefinition.arn
        }


class FakeContainerInstance(object):

    RESOURCES = {
        "t2.micro": (1024, 1024),
        "m1.small": (1024, 1700),
    }

    def __init__(self, instance):
        self.agentConnected = True
        self.agentUpdateStatus = 'OK'
        self.containerInstanceArn = "arn:aws:ecs:us-west-2:012345678910:container-instance/{}".format(str(uuid.uuid4()))
        self.ec2Instance = instance
        self.pendingTasksCount = 0
        self.runningTasksCount = 0
        self.status = 'ACTIVE'
        self.tasks = []

    def registeredResources(self):
        tasks = [t for t in self.tasks if t.desiredStatus == 'RUNNING']
        cpu, memory = 0, 0
        for task in tasks:
            used_cpu, used_memory = task.taskDefinition.consumes()
            cpu = cpu + used_cpu
            memory = memory + used_memory
        return cpu, memory

    def remainingResources(self):
        totalCPU, totalMemory = self.RESOURCES[self.ec2Instance.instance_type]
        usedCPU, usedMemory = self.registeredResources()
        return (totalCPU - usedCPU, totalMemory - usedMemory)

    def _integer_resource(self, name, value):
        return {
            "doubleValue": 0,
            "integerValue": value,
            "longValue": 0,
            "name": name,
            "type": "INTEGER"
        }

    def to_json(self):
        usedCPU, usedMemory = self.registeredResources()
        totalCPU, totalMemory = self.RESOURCES[self.ec2Instance.instance_type]
        return {
            "containerInstanceArn": self.containerInstanceArn,
            "ec2InstanceId": self.ec2Instance.id,
            "pendingTasksCount": len([t for t in self.tasks
                                     if t.desiredStatus == 'PENDING']),
            "runningTasksCount": len([t for t in self.tasks
                                     if t.desiredStatus == 'RUNNING']),
            "agentConnected": True,
            "registeredResources": [
                self._integer_resource("CPU", usedCPU),
                self._integer_resource("MEMORY", usedMemory)],
            "remainingResources": [
                self._integer_resource("CPU", totalCPU - usedCPU),
                self._integer_resource("MEMORY", totalMemory - usedMemory)],
            "status": self.status,
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
        self.tasks = []
        self.instances = []

    def __str__(self):
        return self.clusterName

    @classmethod
    def create_from_cloudformation_json(cls, resource_name, cloudformation_json, region_name):
        backend = ec2containerservice_backends[region_name]
        return backend.create_cluster(resource_name)

    def register_container_instance(self, instance):
        """Register a EC2 instance in the cluster.

        :type instance: `moto.ec2.models.Instance`
        """
        print "REGISTER", instance
        self.instances.append(FakeContainerInstance(instance))

    def list_container_instances(self):
        return self.instances

    def describe_container_instances(self, containerInstances):
        remaining = containerInstances[:]
        failures = []
        instances = []
        for instance in self.instances:
            if instance.containerInstanceArn in remaining:
                remaining.remove(instance.containerInstanceArn)
                instances.append(instance)
        for arn in remaining:
            failures.append({
                "arn": arn,
                "reason": "MISSING"
            })
        return failures, instances

    def create_service(self, serviceName, taskDefinition, desiredCount):
        service = FakeService(self, serviceName)
        service.update(taskDefinition, desiredCount)
        self.services.append(service)
        return service

    def get_service(self, serviceArn):
        for service in self.services:
            if service.serviceArn == serviceArn:
                return service

    def update_service(self, service, taskDefinition, desiredCount):
        service = self.get_service(service)
        service.update(taskDefinition, desiredCount)
        return service

    def schedule(self, task):
        required_cpu, required_memory = task.taskDefinition.consumes()
        for instance in self.instances:
            remaining_cpu, remaining_memory = instance.remainingResources()
            print instance.ec2Instance, "required", required_cpu, required_memory, "remaining", remaining_cpu, remaining_memory
            if (remaining_cpu >= required_cpu and remaining_memory >= required_memory):
                task.assign(instance)
                break
        print "DONE ASSIGN"

    def run_tasks(self, count, overrides, startedBy, taskDefinition,
                  service=None):
        for _ in range(count):
            task = FakeTask(self, taskDefinition, service,
                            startedBy, overrides)
            self.tasks.append(task)
            self.schedule(task)

    def list_tasks(self, containerInstance, desiredStatus, family,
                   serviceName, startedBy=None):
        tasks = self.tasks[:]
        if containerInstance:
            pass
        if desiredStatus:
            tasks = filter(
                lambda task: task.desiredStatus == desiredStatus,
                tasks)
        else:
            tasks = filter(
                lambda task: task.desiredStatus != 'STOPPED',
                tasks)
        if family:
            tasks = filter(
                lambda task: task.taskDefinition.family == family,
                tasks)
        if serviceName:
            tasks = filter(
                lambda task: task.service and task.service.serviceName == serviceName,
                tasks)
        if startedBy:
            tasks = filter(
                lambda task: task.startedBy == startedBy,
                tasks)
        return tasks

    def describe_tasks(self, taskArns):
        failures = []
        tasks = []
        mapping = dict([(task.taskArn, task) for task in self.tasks])
        for taskArn in taskArns:
            task = mapping.get(taskArn)
            if not task:
                failures.append({
                    "arn": taskArn,
                    "reason": "MISSING"
                })
            else:
                tasks.append(task)
        return failures, tasks

    def to_json(self):
        runningTasksCount = len([
            task
            for instance in self.instances
            for task in instance.tasks
            if task.lastStatus == 'RUNNING'
        ])
        pendingTasksCount = len([
            task
            for instance in self.instances
            for task in instance.tasks
            if task.lastStatus == 'PENDING'
        ])
        return {
            "activeServicesCount": len(self.services),
            "clusterArn": self.clusterArn,
            "clusterName": self.clusterName,
            "pendingTasksCount": pendingTasksCount,
            "runningTasksCount": runningTasksCount,
            "registeredContainerInstancesCount": len(self.instances),
            "status": self.status
            }


class TaskDefinition(object):

    def __init__(self, family, containerDefinitions, volumes):
        self.family = family
        self.containerDefinitions = containerDefinitions
        self.volumes = volumes
        self.status = 'UNKNOWN'
        self.revision = '1'
        self.arn = "arn:aws:ecs:us-east-1:012345678910:task-definition/{}:{}/{}".format(
            self.family, self.revision, str(uuid.uuid4()))

    def to_json(self):
        return {
            "containerDefinitions": self.containerDefinitions,
            "family": self.family,
            "revision": self.revision,
            "status": self.status,
            "taskDefinitionArn": self.arn,
            "volumes": self.volumes
        }

    def consumes(self):
        cpu, memory = 0, 0
        for containerDefinition in self.containerDefinitions:
            cpu += containerDefinition.get('cpu', 0)
            memory += containerDefinition.get('memory', 0)
        return cpu, memory



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

    def create_cluster(self, cluster_name):
        cluster = FakeCluster(cluster_name)
        self.clusters.append(cluster)
        return cluster

    def describe_clusters(self, cluster_names):
        failures, clusters = [], []
        for name in cluster_names:
            cluster = self._get_cluster(name)
            if cluster is None:
                failures.append({
                    "arn": name,
                    "reason": "MISSING"
                })
            else:
                clusters.append(cluster)
        return failures, clusters

    def list_container_instances(self, cluster):
        cluster = self._get_cluster(cluster)
        return cluster.list_container_instances()

    def describe_container_instances(self, cluster, containerInstanceArns):
        cluster = self._get_cluster(cluster)
        return cluster.describe_container_instances(containerInstanceArns)

    def register_task_definition(self, family, containerDefinitions, volumes):
        taskDefinition = TaskDefinition(family, containerDefinitions, volumes)
        self.taskDefinitions.append(taskDefinition)
        return taskDefinition

    def create_service(self, cluster, serviceName, taskDefinition, desiredCount):
        cluster = self._get_cluster(cluster)
        taskDefinition = self._get_task_definition(taskDefinition)
        assert taskDefinition
        return cluster.create_service(serviceName, taskDefinition, desiredCount)

    def list_services(self, cluster):
        cluster = self._get_cluster(cluster)
        serviceArns = [service.serviceArn for service in cluster.services]
        return serviceArns

    def update_service(self, cluster, service, taskDefinition, desiredCount):
        cluster = self._get_cluster(cluster)
        print "UPDATE", taskDefinition
        taskDefinition = self._get_task_definition(taskDefinition)
        return cluster.update_service(service, taskDefinition, desiredCount)

    def list_tasks(self, cluster, containerInstance, desiredStatus,
                   family, serviceName):
        cluster = self._get_cluster(cluster)
        return cluster.list_tasks(containerInstance, desiredStatus,
                                  family, serviceName)

    def describe_tasks(self, cluster, tasks):
        cluster = self._get_cluster(cluster)
        return cluster.describe_tasks(tasks)

    def describe_services(self, cluster, serviceArns):
        cluster = self._get_cluster(cluster)
        failures = []
        services = []
        for serviceArn in serviceArns:
            service = cluster.get_service(serviceArn)
            if service is None:
                failures.append({
                    "arn": serviceArn,
                    "reason": "MISSING"
                })
            else:
                services.append(service)
        return failures, services


ec2containerservice_backends = {}
for region in boto.ec2containerservice.regions():
    ec2containerservice_backends[region.name] = EC2ContainerServiceBackend()
