FROM jupyter/base-notebook:python-3.11

USER root

# Install Python dependencies. requirements.txt pins psycopg2-binary, which
# ships a self-contained prebuilt wheel (libpq statically bundled), so no
# system libpq/compiler is needed at build time. Add apt packages here only if
# you introduce a dependency that requires compilation from source.

USER $NB_UID

COPY --chown=$NB_UID:$NB_GID starter_code/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

WORKDIR /home/jovyan/work

# No CMD/ENTRYPOINT on purpose: the launch command (start-notebook.py with the
# token/password flags) is supplied by the `jupyter` service in
# podman-compose.yml, and the base image already provides a sensible default.
