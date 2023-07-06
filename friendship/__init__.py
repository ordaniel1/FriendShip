#this file tells python that this is a package and it also intializes and tied together everything that we need
#for our app
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager

from neo4j import GraphDatabase
from py2neo import Graph


app = Flask(__name__)

#in python interpreter : import secrets and then  secrets.token_hex(16)
app.config['SECRET_KEY'] ='c6976081d014b532c359ab49686caa8c'
app.config['SQLALCHEMY_DATABASE_URI'] ='sqlite:///site.db' #db configuration
db= SQLAlchemy(app)
bcrypt = Bcrypt(app) #for passowrds
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category ='info' #nicely colored blue information alert (bootstrap)


#grpahDB - neo4j

neo4j_uri = "neo4j+s://2e83e0a1.databases.neo4j.io"  #Neo4j server URI
neo4j_user = "neo4j"  # Neo4j username
neo4j_password = "HVkqV7NjoFb72eY7XX0co07ADI_p_y4_cuOMeYZXsAw"  # Neo4j password

# Create a global Neo4j graph instance
neo4j_graph = Graph(neo4j_uri, auth=(neo4j_user, neo4j_password))
neo4j_driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))




#imopot here to avoid circular imports
from friendship import routes