"Users database."

import hashlib
import os
from pathlib import Path
import uuid

import yaml

import constants


class User:
    "User entity."

    _keys = ["role", "email", "password", "salt", "name", "apikey", "code"]

    def __init__(self, id, **data):
        self.id = id
        for key in self._keys:
            setattr(self, key, data.get(key))

    def __str__(self):
        return self.id

    def __repr__(self):
        return f"User('{self.id}')"

    def to_dict(self):
        result = {"id": self.id}
        for key in self._keys:
            result[key] = getattr(self, key)
        return result

    def login(self, password):
        "Return True of the password matches."
        h = hashlib.sha256()
        h.update(self.salt.encode(constants.ENCODING))
        h.update(password.encode(constants.ENCODING))
        return h.hexdigest() == self.password

    def set_password(self, new):
        "Set the password for the user."
        salt = uuid.uuid4().hex.encode(constants.ENCODING)
        h = hashlib.sha256()
        h.update(salt)
        h.update(new.encode(constants.ENCODING))
        self.salt = salt.decode()
        self.password = h.hexdigest()

    def set_apikey(self):
        "Set a new API key for the user."
        self.apikey = uuid.uuid4().hex

    def reset_password(self):
        "Reset the password for the user, setting the code required to edit password."
        self.salt = None
        self.password = None
        self.code = uuid.uuid4().hex

    @property
    def is_admin(self):
        return self.role == constants.ADMIN_ROLE


class Database:
    "In-memory users database."

    def __init__(self):
        self.filepath = (
            Path(os.environ["WRITETHATBOOK_DIR"]) / constants.USERS_DATABASE_FILENAME
        )
        self.read()

    def __enter__(self):
        return self

    def __exit__(self, type, value, tb):
        if type is None:
            self.write()
        return False

    def __len__(self):
        return len(self.users)

    def read(self):
        "Read the entire database."
        self.users = {}
        try:
            with self.filepath.open() as infile:
                for data in yaml.safe_load(infile.read())["users"]:
                    id = data.pop("id")
                    self.users[id] = User(id, **data)
        except FileNotFoundError:
            pass

    def write(self):
        "Write the entire database."
        with self.filepath.open("w") as outfile:
            outfile.write(
                yaml.dump(
                    dict(users=list(u.to_dict() for u in self.users.values())),
                    allow_unicode=True,
                )
            )

    def __getitem__(self, key):
        """Get the user given the userid.
        Otherwise raise KeyError.
        """
        for user in self.users.values():
            if user.id == key:
                return user
        raise KeyError(f"no such user '{key}'")

    def __contains__(self, key):
        try:
            bool(self[key])
        except KeyError:
            return False

    def get(self, userid=None, email=None, apikey=None, default=None):
        "Get the user given the userid, email or API key, or return default value."
        try:
            if userid:
                return self[userid]
        except KeyError:
            pass
        for user in self.users.values():
            if email and user.email == email:
                return user
            if apikey and user.apikey == apikey:
                return user
        return default

    def create_user(self, userid, role=constants.USER_ROLE):
        "Create a new user. NOTE: Does not write out the database."
        if userid in self:
            raise KeyError(f"user '{userid}' already registered")
        if role not in constants.ROLES:
            raise ValueError(f"Invalid user role value '{role}'")
        self.users[userid] = user = User(id=userid, role=role)
        return user

    def all(self):
        for u in sorted(self.users.values(), key=lambda u: u.id):
            yield u


# Singleton instance of in-memory users database.
database = Database()


def get(userid):
    return database.get(userid=userid)


def set_current_user(request, session):
    "Set current user, if available in session. To be used as 'before' function."
    try:
        user = database[session.get("auth")]
    except KeyError:
        try:
            user = database.get(apikey=request.headers["apikey"])
            if not user:
                raise KeyError
        except KeyError:
            return
    request.scope["current_user"] = user


def initialize():
    """Add the system user (owner of refs book), if not done.
    Add admin-role user specified by environment variables,
    or update its password if it exists.
    """
    if constants.SYSTEM_USERID not in database:
        with database as db:
            db.create_user(constants.SYSTEM_USERID, role=constants.ADMIN_ROLE)
    try:
        userid = os.environ["WRITETHATBOOK_USERID"]
        password = os.environ["WRITETHATBOOK_PASSWORD"]
    except KeyError:
        return
    try:
        user = database[userid]
    except KeyError:
        with database as db:
            user = db.create_user(userid, role=constants.ADMIN_ROLE)
            user.set_password(password)
            user.set_apikey()
        print("Initialize users: added", userid)
    else:
        if not user.login(password):
            with database as db:
                user.set_password(password)
                user.set_apikey()
            print("Initialize users: changed password for", userid)


if __name__ == "__main__":
    initialize()
