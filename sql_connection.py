from flask import Flask, render_template, request, session, redirect, url_for, flash
from functools import wraps
import cx_Oracle
import hashlib
import os

### FLASK SETUP ###

app = Flask(__name__)
app.secret_key='letstipit'

### SQL SETUP ###
oracle_user = "system"
oracle_password = os.environ.get("SQL_PASS")  #well need to set this in the environment
oracle_host = "localhost"
oracle_port = "1521"
oracle_service = "XEPDB1"  #default pluggable database in XE 21c

dsn = cx_Oracle.makedsn(oracle_host, oracle_port, service_name=oracle_service)


### FUNCTIONS ###
def get_connection():
    connection = cx_Oracle.connect(user=oracle_user, password=oracle_password, dsn=dsn)
    print("connected to Oracle XE")
    return connection

def get_app():
    return app
