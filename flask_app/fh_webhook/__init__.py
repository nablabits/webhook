import os
import json
from datetime import datetime

from flask import Flask, request, Response
from flask_migrate import Migrate
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from config import TestingConfig
from fh_webhook.models import db

from decouple import config


def create_app(test_config=False):
    """Serve the entry points for the webhook."""
    app = Flask(__name__, instance_relative_config=True)
    if test_config:
        app.config.from_object(TestingConfig)
    else:
        app.config.from_object(config("APP_SETTINGS"))
    db.init_app(app)
    Migrate(app, db)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # load auth
    auth = HTTPBasicAuth()
    fh_pass = app.config["FH_PASSWORD"]
    users = {"fareharbor": generate_password_hash(fh_pass), }
    test_pass = app.config.get("TEST_PASSWORD")
    if test_pass:
        users["test"] = generate_password_hash(test_pass)

    @auth.verify_password
    def verify_password(username, password):
        user_exists = username in users
        # has_valid_pass = check_password_hash(users.get(username), password)
        if user_exists and check_password_hash(users.get(username), password):
            return username

    @app.route("/test_webhook", methods=["POST"])
    @auth.login_required
    def save_content():
        """Save the content of the POST method in a JSON file.

        If the response is empty it logs the event.

        Before storing the data on the db we should know how that data looks
        to create the tables accordingly. So we need a way to store the data
        to inspect it.
        """
        path = "fh_webhook/responses/"
        try:
            os.makedirs(path)
        except OSError:
            pass
        now = datetime.now()
        if request.json:

            # Dump the content onto a file
            name = str(now.timestamp()) + ".json"
            filename = os.path.join(path, name)
            with open(filename, "w") as fp:
                json.dump(request.json, fp)

            # if we are testing we should return the filename somehow
            try:
                request.json["test"]
                return app.make_response(filename)
            except KeyError:
                return Response(status=200)
        else:
            with open(os.path.join(path, "errors.log"), "a") as f:
                f.write("{} - the request was empty\n".format(now))
            return Response("The request was empty", status=400)

    @app.route("/webhook", methods=["POST"])
    def respond():
        """Future official entry point."""
        return Response(status=200)

    @app.route("/", methods=["GET"])
    def index():
        """Quick check that the server is running."""
        app_name = os.getenv("APP_NAME")
        if app_name:
            return "Hello from flask on a Docker environment"
        return "Hello from Flask"
    return app
