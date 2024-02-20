# AMS Operator

Anbox Cloud offers a software stack that runs Android applications in any cloud enabling high-performance
streaming of graphics to desktop and mobile client devices.

At its heart, it uses lightweight container technology instead of full virtual machines to achieve higher
density and better performance per host while ensuring security and isolation of each container. Depending
on the target platform, payload, and desired application performance (e.g. frame rate), more than
100 containers can be run on a single machine.

For containerization of Android, Anbox Cloud uses the well established and secure container hypervisor
LXD. LXD is secure by design, scales to a large number of containers and provides advanced resource
management for hosted containers.

Also have a look at the official Anbox Cloud website (https://anbox-cloud.io) for more information.

> NOTE: Anbox Cloud is a paid offering. You will need a [Ubuntu Pro](https://ubuntu.com/pro) subscription
> for this charm to work. To achieve this with `juju` another charm can be used to attach the machine to
> the AMS Operator. The [ubuntu-advantage](https://charmhub.io/ubuntu-advantage) acts as a subordinate charm
> to attach the machine to Pro.

## Anbox Management System

The Anbox Management System, or *ams* is the main piece of software responsible for managing containers,
applications, addons, and more.

Running the `AMS` charm requires other charms to be deployed beforehand.

```sh
$ juju deploy etcd
$ juju deploy easyrsa
$ juju relate etcd easyrsa
```

Then deploy `ams`

```sh
$ juju deploy ams
$ juju relate ams etcd
```

For more information about AMS, visit the official documentation on https://anbox-cloud.io
