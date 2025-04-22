from flask import Flask, render_template, request, session, redirect, url_for, flash
from functools import wraps
import cx_Oracle
import hashlib
import os

### FLASK SETUP ###

app = Flask(__name__)
app.secret_key='letstripit'

### SQL SETUP ###
oracle_user = "tripsync"
oracle_password = "tripsync"  #well need to set this in the environment
oracle_host = "localhost"
oracle_port = "1539"
oracle_service = "XE"  #default pluggable database in XE 21c

dsn = cx_Oracle.makedsn(oracle_host, oracle_port, service_name=oracle_service)


### FUNCTIONS ###
def get_connection():
    connection = cx_Oracle.connect(user=oracle_user, password=oracle_password, dsn=dsn)
    print("connected to Oracle XE")
    return connection

def get_app():
    return app
