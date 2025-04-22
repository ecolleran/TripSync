import datetime

import oracledb
import db_config

con = oracledb.connect(user=db_config.user, password=db_config.pw, dsn=db_config.dsn)


def insert_user(username, first_name, last_name, email):
    date_joined = datetime.now()

    
    
