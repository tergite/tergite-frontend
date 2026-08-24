# tergite-frontend

[![Frontend CI](https://github.com/tergite/tergite-frontend/actions/workflows/frontend-ci.yml/badge.svg)](https://github.com/tergite/tergite-frontend/actions/workflows/frontend-ci.yml)

The Frontend in the [Tergite software stack](https://tergite.github.io/) of the WACQT quantum computer.

**This project is developed by a core group of collaborators.**
**Chalmers Next Labs AB (CNL) takes on the role of managing and maintaining this project.**

![Login screen](./apps/tergite-dashboard/docs/assets/login-screen.png)
The login screen

![Home screen](./apps/tergite-dashboard/docs/assets/home-screen.png)
The home screen

![Tergite dashboard showcase](./apps/tergite-dashboard/docs/assets/dashboard-showcase.gif)
A preview of the the dashboard

## Version Control

The tergite stack is developed on a separate version control system and mirrored on Github.
If you are reading this on GitHub, then you are looking at a mirror.

## Services

- [Tergite Dashboard](./apps/tergite-dashboard/) [![Dashboard CI](https://github.com/tergite/tergite-frontend/actions/workflows/dashboard-ci.yml/badge.svg)](https://github.com/tergite/tergite-frontend/actions/workflows/dashboard-ci.yml)  
  The website that shows the state of the quantum computer
- [Tergite Main Service Server or MSS](./apps/tergite-mss/) [![MSS CI](https://github.com/tergite/tergite-frontend/actions/workflows/mss-ci.yml/badge.svg)](https://github.com/tergite/tergite-frontend/actions/workflows/mss-ci.yml)  
  The server that controls all services on this frontend.  
  It also exposes the REST API through which other clients like [tergite SDK](https://github.com/tergite/tergite) communicate with the quantum computers.

## Dependencies

- [docker +v23.0.5](https://www.docker.com/products/docker-desktop/)
- [docker compose](https://docs.docker.com/compose/)
- Linux OS if the `LOGGING_DRIVER` variable in `.env` is set to 'journald' (**recommended**) since [journald is only for Linux](https://forums.docker.com/t/docker-for-windows-logging-failed-to-initialize-logging-driver-journald-is-not-enabled-on-this-host/68690/4).  
  _One could use the default `json-file` logging driver but this would quickly fill up one's disk space after some time. See [here](https://docs.docker.com/config/containers/logging/configure/)_.  
  _One could also use the `local` logging driver but external tools like promtail, our logging aggregator client, cannot work with it. See [here](https://docs.docker.com/config/containers/logging/local/)_

## Getting Started

- Ensure you have [docker](https://docs.docker.com/engine/install/) installed.

- Clone the repo

```shell
git clone git@github.com:tergite/tergite-frontend.git
```

- You might need to login to a hosted docker container registry e.g. one based on the [tergite-registry repo](https://github.com/tergite/tergite-registry),
  especially if you are going to use prebuilt tergite images.

```shell
# e.g. if container registry is hosted at example.com:8002
# and username is johndoe
# and password is password123
CONTAINER_REGISTRY=example.com:8002
DOCKER_USERNAME=johndoe
# feed in password when prompted
docker login ${CONTAINER_REGISTRY} -u $DOCKER_USERNAME
```

- Copy the `mss-config.example.toml` to `mss-config.toml` and update the configuration there.

```shell
cd tergite-frontend
cp mss-config.example.toml mss-config.toml
```

- Create a `.env` file basing on the `.env.example` file.
  Update the variables therein appropriately.

```shell
cp .env.example .env
```

- To rebuild and run the services, use the `fresh-docker-compose.yml`

```shell
docker compose -f fresh-docker-compose.yml up -d
```

- To use prebuilt images to run the services, use the `prebuilt-docker-compose.yml`

```shell
docker compose -f prebuilt-docker-compose.yml up -d
```

- Open your browser at

  - [http://localhost:8002](http://localhost:8002) to see the MSS service
  - [http://localhost:3000](http://localhost:3000) to see the dashboard application

- To ensure that the services start up even on server restarts, run:

```shell
sudo systemctl enable docker
```

- To stop the services, run:

```shell
docker compose -f fresh-docker-compose.yml stop
```

or for prebuilt:

```shell
docker compose -f prebuilt-docker-compose.yml stop
```

- To remove stop the services and remove their containers also, run:

```shell
docker compose -f fresh-docker-compose.yml down
```

or for prebuilt:

```shell
docker compose -f prebuilt-docker-compose.yml down
```

## How to Run wi

## FAQ

### Why can't I access the service?

It could be an issue with your iptables. Check them.

- You could set qal9000 behind an nginx reverse proxy pointing ports 80,443 to the landing page URL (http://localhost:8030), but don't forget to open up your firewall to allow connections on 80,443 ports

```shell
sudo iptables -I INPUT -p tcp -m state --state NEW -m tcp -m multiport --dports 80,443 -j ACCEPT
```

You could add `-s nnn.nnn.n.n/nn ` arg to the above command to limit access to only a given subnet e.g. `-s 255.255.0.0/16`

### Why aren't rules set in ufw working?

When docker is installed, it adds its own `iptables` rules which open all ports by default to the entire world. See [this article](https://docs.docker.com/network/packet-filtering-firewalls/) for more information. In order to customize these rules, new rules have to be added to the DOCKER-USER chain.

You can add other rules in the same DOCKER-USER chain, carefully :-)

## Contribution Guidelines

If you would like to contribute to tergite-frontend, please have a look at our [contribution guidelines](./CONTRIBUTING.md)

## Authors

This project is a work of
[many contributors](https://github.com/tergite/tergite-frontend/graphs/contributors).

Special credit goes to the authors of this project as seen in the [CREDITS](./CREDITS.md) file.

## ChangeLog

To view the changelog for each version, have a look at the [CHANGELOG.md](./CHANGELOG.md) file.

## License

[Apache 2.0 License](./LICENSE)

## TODO

- [ ] There is no feedback to the user after submitting the request access form.
    - Maybe show a toast or redirect to past requests screen
- [ ] Make the 'Project External ID' input an autocomplete
    - Maybe add a read-only autocomplete GET endpoint for project IDs
    - Make the input autocomplete with shadcn `Combobox`
- [ ] There is no screen for users to view their past project access requests and their status
    - Add a sidebar nav item (we could add it as a child of say Projects or Access since we might have too many items in the sidebar) for access requests
      - Similar style to 'Admin' submenu in the sidebar
- [ ] Pending User requests for the admin probably need to have a quick response set of buttons in the table so that admins quickly approve multiple requests instead of opening each one first
- [ ] Approving a project access request fails with

  ```JSON
  {"timestamp": "2026-08-24T12:44:25.022575+00:00", "level": "ERROR", "message": "Exception in ASGI application\n", "logger": "logging", "file": "__init__.py:1762", "function": "callHandlers", "process_id": 53, "thread_id": 281473397472552, "exception": {"type": "OperationFailure", "value": "Plan executor error during findAndModify :: caused by :: Cannot apply $addToSet to non-array field. Field named 'user_emails' has non-array type null, full error: {'ok': 0.0, 'errmsg': \"Plan executor error during findAndModify :: caused by :: Cannot apply $addToSet to non-array field. Field named 'user_emails' has non-array type null\", 'code': 2, 'codeName': 'BadValue'}", "traceback": "  + Exception Group Traceback (most recent call last):\n  |   File \"/usr/local/lib/python3.12/site-packages/starlette/_utils.py\", line 76, in collapse_excgroups\n  |     yield\n  |   File \"/usr/local/lib/python3.12/site-packages/starlette/middleware/base.py\", line 177, in __call__\n  |     async with anyio.create_task_group() as task_group:\n  |                ^^^^^^^^^^^^^^^^^^^^^^^^^\n  |   File \"/usr/local/lib/python3.12/site-packages/anyio/_backends/_asyncio.py\", line 815, in __aexit__\n  |     raise BaseExceptionGroup(\n  | ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)\n  +-+---------------- 1 ----------------\n    | Traceback (most recent call last):\n    |   File \"/usr/local/lib/python3.12/site-packages/uvicorn/protocols/http/h11_impl.py\", line 416, in run_asgi\n    |     result = await app(  # type: ignore[func-returns-value]\n    |              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n    |   File \"/usr/local/lib/python3.12/site-packages/uvicorn/middleware/proxy_headers.py\", line 63, in __call__\n    |     return await self.app(scope, receive, send)\n    |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n    |   File \"/usr/local/lib/python3.12/site-packages/fastapi/applications.py\", line 1054, in __call__\n    |     await super().__call__(scope, receive, send)\n    |   File \"/usr/local/lib/python3.12/site-packages/starlette/applications.py\", line 112, in __call__\n    |     await self.middleware_stack(scope, receive, send)\n    |   File \"/usr/local/lib/python3.12/site-packages/starlette/middleware/errors.py\", line 187, in __call__\n    |     raise exc\n    |   File \"/usr/local/lib/python3.12/site-packages/starlette/middleware/errors.py\", line 165, in __call__\n    |     await self.app(scope, receive, _send)\n    |   File \"/usr/local/lib/python3.12/site-packages/starlette/middleware/base.py\", line 176, in __call__\n    |     with recv_stream, send_stream, collapse_excgroups():\n    |                                    ^^^^^^^^^^^^^^^^^^^^\n    |   File \"/usr/local/lib/python3.12/contextlib.py\", line 158, in __exit__\n    |     self.gen.throw(value)\n    |   File \"/usr/local/lib/python3.12/site-packages/starlette/_utils.py\", line 82, in collapse_excgroups\n    |     raise exc\n    |   File \"/usr/local/lib/python3.12/site-packages/starlette/middleware/base.py\", line 178, in __call__\n    |     response = await self.dispatch_func(request, call_next)\n    |                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n    |   File \"/code/api/rest/__init__.py\", line 107, in request_logging_middleware\n    |     raise exc\n    |   File \"/code/api/rest/__init__.py\", line 90, in request_logging_middleware\n    |     response = await call_next(request)\n    |                ^^^^^^^^^^^^^^^^^^^^^^^^\n    |   File \"/usr/local/lib/python3.12/site-packages/starlette/middleware/base.py\", line 156, in call_next\n    |     raise app_exc\n    |   File \"/usr/local/lib/python3.12/site-packages/starlette/middleware/base.py\", line 141, in coro\n    |     await self.app(scope, receive_or_disconnect, send_no_error)\n    |   File \"/usr/local/lib/python3.12/site-packages/starlette/middleware/cors.py\", line 93, in __call__\n    |     await self.simple_response(scope, receive, send, request_headers=headers)\n    |   File \"/usr/local/lib/python3.12/site-packages/starlette/middleware/cors.py\", line 144, in simple_response\n    |     await self.app(scope, receive, send)\n    |   File \"/usr/local/lib/python3.12/site-packages/starlette/middleware/exceptions.py\", line 62, in __call__\n    |     await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)\n    |   File \"/usr/local/lib/python3.12/site-packages/starlette/_exception_handler.py\", line 53, in wrapped_app\n    |     raise exc\n    |   File \"/usr/local/lib/python3.12/site-packages/starlette/_exception_handler.py\", line 42, in wrapped_app\n    |     await app(scope, receive, sender)\n    |   File \"/usr/local/lib/python3.12/site-packages/starlette/routing.py\", line 714, in __call__\n    |     await self.middleware_stack(scope, receive, send)\n    |   File \"/usr/local/lib/python3.12/site-packages/starlette/routing.py\", line 734, in app\n    |     await route.handle(scope, receive, send)\n    |   File \"/usr/local/lib/python3.12/site-packages/starlette/routing.py\", line 288, in handle\n    |     await self.app(scope, receive, send)\n    |   File \"/usr/local/lib/python3.12/site-packages/starlette/routing.py\", line 76, in app\n    |     await wrap_app_handling_exceptions(app, request)(scope, receive, send)\n    |   File \"/usr/local/lib/python3.12/site-packages/starlette/_exception_handler.py\", line 53, in wrapped_app\n    |     raise exc\n    |   File \"/usr/local/lib/python3.12/site-packages/starlette/_exception_handler.py\", line 42, in wrapped_app\n    |     await app(scope, receive, sender)\n    |   File \"/usr/local/lib/python3.12/site-packages/starlette/routing.py\", line 73, in app\n    |     response = await f(request)\n    |                ^^^^^^^^^^^^^^^^\n    |   File \"/usr/local/lib/python3.12/site-packages/fastapi/routing.py\", line 301, in app\n    |     raw_response = await run_endpoint_function(\n    |                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n    |   File \"/usr/local/lib/python3.12/site-packages/fastapi/routing.py\", line 212, in run_endpoint_function\n    |     return await dependant.call(**values)\n    |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n    |   File \"/code/api/rest/routers/admin.py\", line 231, in update_user_request\n    |     result = await user_requests.update(_id, payload=body, admin_user=user)\n    |              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n    |   File \"/code/services/auth/user_requests/__init__.py\", line 370, in update\n    |     await _apply_approval(request)\n    |   File \"/code/services/auth/user_requests/__init__.py\", line 411, in _apply_approval\n    |     project = await Project.find_one(\n    |               ^^^^^^^^^^^^^^^^^^^^^^^\n    |   File \"/usr/local/lib/python3.12/site-packages/beanie/odm/queries/update.py\", line 346, in __await__\n    |     update_result = yield from self._update().__await__()\n    |                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n    |   File \"/usr/local/lib/python3.12/site-packages/beanie/odm/queries/update.py\", line 315, in _update\n    |     result = await self.document_model.get_motor_collection().find_one_and_update(\n    |              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n    |   File \"/usr/local/lib/python3.12/concurrent/futures/thread.py\", line 59, in run\n    |     result = self.fn(*self.args, **self.kwargs)\n    |              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n    |   File \"/usr/local/lib/python3.12/site-packages/pymongo/synchronous/collection.py\", line 3680, in find_one_and_update\n    |     return self._find_and_modify(\n    |            ^^^^^^^^^^^^^^^^^^^^^^\n    |   File \"/usr/local/lib/python3.12/site-packages/pymongo/synchronous/collection.py\", line 3321, in _find_and_modify\n    |     return self._database.client._retryable_write(\n    |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n    |   File \"/usr/local/lib/python3.12/site-packages/pymongo/synchronous/mongo_client.py\", line 2113, in _retryable_write\n    |     return self._retry_with_session(retryable, func, s, bulk, operation, operation_id)\n    |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n    |   File \"/usr/local/lib/python3.12/site-packages/pymongo/synchronous/mongo_client.py\", line 1986, in _retry_with_session\n    |     return self._retry_internal(\n    |            ^^^^^^^^^^^^^^^^^^^^^\n    |   File \"/usr/local/lib/python3.12/site-packages/pymongo/_csot.py\", line 125, in csot_wrapper\n    |     return func(self, *args, **kwargs)\n    |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^\n    |   File \"/usr/local/lib/python3.12/site-packages/pymongo/synchronous/mongo_client.py\", line 2038, in _retry_internal\n    |     ).run()\n    |       ^^^^^\n    |   File \"/usr/local/lib/python3.12/site-packages/pymongo/synchronous/mongo_client.py\", line 2811, in run\n    |     res = self._read() if self._is_read else self._write()\n    |                                              ^^^^^^^^^^^^^\n    |   File \"/usr/local/lib/python3.12/site-packages/pymongo/synchronous/mongo_client.py\", line 3014, in _write\n    |     return self._func(self._session, conn, self._retryable)  # type: ignore\n    |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n    |   File \"/usr/local/lib/python3.12/site-packages/pymongo/synchronous/collection.py\", line 3307, in _find_and_modify_helper\n    |     out = self._command(\n    |           ^^^^^^^^^^^^^^\n    |   File \"/usr/local/lib/python3.12/site-packages/pymongo/synchronous/collection.py\", line 615, in _command\n    |     return conn.command(\n    |            ^^^^^^^^^^^^^\n    |   File \"/usr/local/lib/python3.12/site-packages/pymongo/synchronous/helpers.py\", line 53, in inner\n    |     return func(*args, **kwargs)\n    |            ^^^^^^^^^^^^^^^^^^^^^\n    |   File \"/usr/local/lib/python3.12/site-packages/pymongo/synchronous/pool.py\", line 403, in command\n    |     return command(\n    |            ^^^^^^^^\n    |   File \"/usr/local/lib/python3.12/site-packages/pymongo/synchronous/network.py\", line 212, in command\n    |     helpers_shared._check_command_response(\n    |   File \"/usr/local/lib/python3.12/site-packages/pymongo/helpers_shared.py\", line 284, in _check_command_response\n    |     raise OperationFailure(errmsg, code, response, max_wire_version)\n    | pymongo.errors.OperationFailure: Plan executor error during findAndModify :: caused by :: Cannot apply $addToSet to non-array field. Field named 'user_emails' has non-array type null, full error: {'ok': 0.0, 'errmsg': \"Plan executor error during findAndModify :: caused by :: Cannot apply $addToSet to non-array field. Field named 'user_emails' has non-array type null\", 'code': 2, 'codeName': 'BadValue'}\n    +------------------------------------\n\nDuring handling of the above exception, another exception occurred:\n\nTraceback (most recent call last):\n  File \"/usr/local/lib/python3.12/site-packages/uvicorn/protocols/http/h11_impl.py\", line 416, in run_asgi\n    result = await app(  # type: ignore[func-returns-value]\n             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/usr/local/lib/python3.12/site-packages/uvicorn/middleware/proxy_headers.py\", line 63, in __call__\n    return await self.app(scope, receive, send)\n           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/usr/local/lib/python3.12/site-packages/fastapi/applications.py\", line 1054, in __call__\n    await super().__call__(scope, receive, send)\n  File \"/usr/local/lib/python3.12/site-packages/starlette/applications.py\", line 112, in __call__\n    await self.middleware_stack(scope, receive, send)\n  File \"/usr/local/lib/python3.12/site-packages/starlette/middleware/errors.py\", line 187, in __call__\n    raise exc\n  File \"/usr/local/lib/python3.12/site-packages/starlette/middleware/errors.py\", line 165, in __call__\n    await self.app(scope, receive, _send)\n  File \"/usr/local/lib/python3.12/site-packages/starlette/middleware/base.py\", line 176, in __call__\n    with recv_stream, send_stream, collapse_excgroups():\n                                   ^^^^^^^^^^^^^^^^^^^^\n  File \"/usr/local/lib/python3.12/contextlib.py\", line 158, in __exit__\n    self.gen.throw(value)\n  File \"/usr/local/lib/python3.12/site-packages/starlette/_utils.py\", line 82, in collapse_excgroups\n    raise exc\n  File \"/usr/local/lib/python3.12/site-packages/starlette/middleware/base.py\", line 178, in __call__\n    response = await self.dispatch_func(request, call_next)\n               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/code/api/rest/__init__.py\", line 107, in request_logging_middleware\n    raise exc\n  File \"/code/api/rest/__init__.py\", line 90, in request_logging_middleware\n    response = await call_next(request)\n               ^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/usr/local/lib/python3.12/site-packages/starlette/middleware/base.py\", line 156, in call_next\n    raise app_exc\n  File \"/usr/local/lib/python3.12/site-packages/starlette/middleware/base.py\", line 141, in coro\n    await self.app(scope, receive_or_disconnect, send_no_error)\n  File \"/usr/local/lib/python3.12/site-packages/starlette/middleware/cors.py\", line 93, in __call__\n    await self.simple_response(scope, receive, send, request_headers=headers)\n  File \"/usr/local/lib/python3.12/site-packages/starlette/middleware/cors.py\", line 144, in simple_response\n    await self.app(scope, receive, send)\n  File \"/usr/local/lib/python3.12/site-packages/starlette/middleware/exceptions.py\", line 62, in __call__\n    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)\n  File \"/usr/local/lib/python3.12/site-packages/starlette/_exception_handler.py\", line 53, in wrapped_app\n    raise exc\n  File \"/usr/local/lib/python3.12/site-packages/starlette/_exception_handler.py\", line 42, in wrapped_app\n    await app(scope, receive, sender)\n  File \"/usr/local/lib/python3.12/site-packages/starlette/routing.py\", line 714, in __call__\n    await self.middleware_stack(scope, receive, send)\n  File \"/usr/local/lib/python3.12/site-packages/starlette/routing.py\", line 734, in app\n    await route.handle(scope, receive, send)\n  File \"/usr/local/lib/python3.12/site-packages/starlette/routing.py\", line 288, in handle\n    await self.app(scope, receive, send)\n  File \"/usr/local/lib/python3.12/site-packages/starlette/routing.py\", line 76, in app\n    await wrap_app_handling_exceptions(app, request)(scope, receive, send)\n  File \"/usr/local/lib/python3.12/site-packages/starlette/_exception_handler.py\", line 53, in wrapped_app\n    raise exc\n  File \"/usr/local/lib/python3.12/site-packages/starlette/_exception_handler.py\", line 42, in wrapped_app\n    await app(scope, receive, sender)\n  File \"/usr/local/lib/python3.12/site-packages/starlette/routing.py\", line 73, in app\n    response = await f(request)\n               ^^^^^^^^^^^^^^^^\n  File \"/usr/local/lib/python3.12/site-packages/fastapi/routing.py\", line 301, in app\n    raw_response = await run_endpoint_function(\n                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/usr/local/lib/python3.12/site-packages/fastapi/routing.py\", line 212, in run_endpoint_function\n    return await dependant.call(**values)\n           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/code/api/rest/routers/admin.py\", line 231, in update_user_request\n    result = await user_requests.update(_id, payload=body, admin_user=user)\n             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/code/services/auth/user_requests/__init__.py\", line 370, in update\n    await _apply_approval(request)\n  File \"/code/services/auth/user_requests/__init__.py\", line 411, in _apply_approval\n    project = await Project.find_one(\n              ^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/usr/local/lib/python3.12/site-packages/beanie/odm/queries/update.py\", line 346, in __await__\n    update_result = yield from self._update().__await__()\n                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/usr/local/lib/python3.12/site-packages/beanie/odm/queries/update.py\", line 315, in _update\n    result = await self.document_model.get_motor_collection().find_one_and_update(\n             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\2026-08-24T12:44:25.037202377Z n  File \"/usr/local/lib/python3.12/concurrent/futures/thread.py\", line 59, in run\n    result = self.fn(*self.args, **self.kwargs)\n             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/usr/local/lib/python3.12/site-packages/pymongo/synchronous/collection.py\", line 3680, in find_one_and_update\n    return self._find_and_modify(\n           ^^^^^^^^^^^^^^^^^^^^^^\n  File \"/usr/local/lib/python3.12/site-packages/pymongo/synchronous/collection.py\", line 3321, in _find_and_modify\n    return self._database.client._retryable_write(\n           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/usr/local/lib/python3.12/site-packages/pymongo/synchronous/mongo_client.py\", line 2113, in _retryable_write\n    return self._retry_with_session(retryable, func, s, bulk, operation, operation_id)\n           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/usr/local/lib/python3.12/site-packages/pymongo/synchronous/mongo_client.py\", line 1986, in _retry_with_session\n    return self._retry_internal(\n           ^^^^^^^^^^^^^^^^^^^^^\n  File \"/usr/local/lib/python3.12/site-packages/pymongo/_csot.py\", line 125, in csot_wrapper\n    return func(self, *args, **kwargs)\n           ^^^^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/usr/local/lib/python3.12/site-packages/pymongo/synchronous/mongo_client.py\", line 2038, in _retry_internal\n    ).run()\n      ^^^^^\n  File \"/usr/local/lib/python3.12/site-packages/pymongo/synchronous/mongo_client.py\", line 2811, in run\n    res = self._read() if self._is_read else self._write()\n                                             ^^^^^^^^^^^^^\n  File \"/usr/local/lib/python3.12/site-packages/pymongo/synchronous/mongo_client.py\", line 3014, in _write\n    return self._func(self._session, conn, self._retryable)  # type: ignore\n           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/usr/local/lib/python3.12/site-packages/pymongo/synchronous/collection.py\", line 3307, in _find_and_modify_helper\n    out = self._command(\n          ^^^^^^^^^^^^^^\n  File \"/usr/local/lib/python3.12/site-packages/pymongo/synchronous/collection.py\", line 615, in _command\n    return conn.command(\n           ^^^^^^^^^^^^^\n  File \"/usr/local/lib/python3.12/site-packages/pymongo/synchronous/helpers.py\", line 53, in inner\n    return func(*args, **kwargs)\n           ^^^^^^^^^^^^^^^^^^^^^\n  File \"/usr/local/lib/python3.12/site-packages/pymongo/synchronous/pool.py\", line 403, in command\n    return command(\n           ^^^^^^^^\n  File \"/usr/local/lib/python3.12/site-packages/pymongo/synchronous/network.py\", line 212, in command\n    helpers_shared._check_command_response(\n  File \"/usr/local/lib/python3.12/site-packages/pymongo/helpers_shared.py\", line 284, in _check_command_response\n    raise OperationFailure(errmsg, code, response, max_wire_version)\npymongo.errors.OperationFailure: Plan executor error during findAndModify :: caused by :: Cannot apply $addToSet to non-array field. Field named 'user_emails' has non-array type null, full error: {'ok': 0.0, 'errmsg': \"Plan executor error during findAndModify :: caused by :: Cannot apply $addToSet to non-array field. Field named 'user_emails' has non-array type null\", 'code': 2, 'codeName': 'BadValue'}\n"}}
  ```
- [ ] After approving a project access request, there is a `Failed to fetch` error:
      ```
      Access to fetch at 'http://127.0.0.1:8002/admin/user-requests/6a8c3bac0c6f8beedba1ad33' from origin 'http://127.0.0.1:3000' has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present on the requested resource.
      TypeError: Failed to fetch
      at ht (index-74TWp7kT.js:288:81530)
      at Object.U7 [as mutationFn] (index-74TWp7kT.js:288:75145)
      at Object.fn (index-74TWp7kT.js:288:42969)
      at C (index-74TWp7kT.js:288:33357)
      at Object.start (index-74TWp7kT.js:288:33816)
      at JA.execute (index-74TWp7kT.js:288:43774)
  fw	@	index-74TWp7kT.js:40
      ```
- [ ] Screens under the Admin sub menu do not show notices and thus user does not see them until user switches to dashboard or devices
    - Probably use similar layout in the admin pages to that used in the dashboard pages
- [ ] Health check requests spam the logs for all apps (MSS, Dashboard, backend)
    - Options:
      - Add a healthcheck endpoint which shows no logs (e.g. the logs to it are filtered out by the server software)? 
      - Reduce information passed in INFO logs. Only ERROR, WARNING and DEBUG probably need such detail of information
- [ ] When a project is created or updated with a given admin, the admin is never notified
      - Add a notification for the user who is made admin
- [ ] When a project is created or updated with a new user or an old user is removed, the given user is not notified
      - Add a notification for all users old and new ensuring that those who have lost access are told so, while those who have been given access
        they didnot have are also notified
- [ ] In project creation and project update forms, make 'Admin email' and 'Member emails' inputs autocomplete for admins
      - Add an admin only autocomplete emails endpoint on MSS
      - Use shadcn's Combobox for those two inputs
- [ ] When Project access requests or QPU time requests are approved or rejected directly and not in the notifications dropdown, the notifications remain intact
      and must be marked 'read' manually.
      - Automatically mark notifications associated with a given user request as read for all approving/rejecting users
- [ ] When new QPU time requests are made by the user, the user does not see the value requested for
      - Options:
        - Redirect to the requests screen with that particular QPU time request open in the detail section
        - Show the value of the number of seconds requested for on the projects page maybe as a badge on the 'Request pending' button
- Handle 503 unavailbale service on the dashboard
- Handle the disconnection issues between MSS and the backends

## Acknowledgements

This project was sponsored by:

- [Knut and Alice Wallenberg Foundation](https://kaw.wallenberg.org/en) under the [Wallenberg Center for Quantum Technology (WACQT)](https://www.chalmers.se/en/centres/wacqt/) project at [Chalmers University of Technology](https://www.chalmers.se)
- [Nordic e-Infrastructure Collaboration (NeIC)](https://neic.no) and [NordForsk](https://www.nordforsk.org/sv) under the [NordIQuEst](https://neic.no/nordiquest/) project
- [European Union's Horizon Europe](https://research-and-innovation.ec.europa.eu/funding/funding-opportunities/funding-programmes-and-open-calls/horizon-europe_en) under the [OpenSuperQ](https://cordis.europa.eu/project/id/820363) project
- [European Union's Horizon Europe](https://research-and-innovation.ec.europa.eu/funding/funding-opportunities/funding-programmes-and-open-calls/horizon-europe_en) under the [OpenSuperQPlus](https://opensuperqplus.eu/) project
