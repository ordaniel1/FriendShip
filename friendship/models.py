from datetime import  datetime
from friendship import db, login_manager, neo4j_graph,neo4j_driver
from flask_login import UserMixin

@login_manager.user_loader
def load_user(user_id):
    return db.session.query(User).get(int(user_id))


#db models that represent the structure of our database

#The User class is a database model representing a user in the application
class User(db.Model, UserMixin): #inheritance from db.Mode and UserMixin
    id = db.Column(db.Integer, primary_key=True)
    username =db.Column(db.String(20), unique=True, nullable=False)
    email =db.Column(db.String(120), unique=True, nullable=False)
    first_name=db.Column(db.String(30), nullable=False)
    last_name=db.Column(db.String(30), nullable=False)
    image_file = db.Column(db.String(20), nullable=False, default='default.jpg')
    password = db.Column(db.String(60))
    country = db.Column(db.String(100),nullable=False)
    city = db.Column(db.String(100),nullable=False)
    phone_code=db.Column(db.String(10),nullable=False)
    phone_number=db.Column(db.String(30),nullable=False)
    is_google_user = db.Column(db.Boolean, nullable=False, default=False) # new field
    google_id = db.Column(db.String(120), unique=True) # new field
    posts = db.relationship('Post', backref='author', lazy=True) #we can use author attribute to get the user who created the post
                                                        #we can also get all of the post created by an individual user
                                    #'posts' is not a column - it runs a query on the post table..
                                    #post.author - print the user details as defined in repr


    help_requests_sent = db.relationship('HelpRequest', backref='sender', lazy=True)

    reviews_received = db.relationship('Review', foreign_keys='Review.reviewed_id', backref=db.backref('reviewed', lazy=True))
    reviews_given = db.relationship('Review', foreign_keys='Review.reviewer_id', backref=db.backref('reviewer', lazy=True))
    notifications = db.relationship('Notification', foreign_keys='Notification.user_id', backref=db.backref('user', lazy=True))
    notifications_sent = db.relationship('Notification', foreign_keys='Notification.sender_id', backref=db.backref('sender', lazy=True))
    unread_notifications_counter =db.Column(db.Integer, default=0)

    sum_rates_as_deliver=db.Column(db.Float, nullable=False ,default=0)
    num_rates_as_deliver=db.Column(db.Integer,nullable=False ,default=0)

    shared_posts = db.relationship('PostShare', backref='user', lazy=True) #IGNORE IT, WE DID NOT USE IT

    def __repr__(self):
        return f"User('{self.id}','{self.username}','{self.email}','{self.image_file}')"


    #retun true if user sent delivery offer to the post
    def has_sent_help_request(self, post):
        help_request = HelpRequest.query.filter_by(sender_id=self.id, post_id=post.id).first()
        if help_request is None:
            return False
        elif help_request.is_cancelled==True:
            return False
        else:
            return True

    #return the help request (delivery offer) that user send to the post (none if they didn't send)
    def get_help_request(self, post_id):
        help_request = HelpRequest.query.filter_by(sender_id=self.id, post_id=post_id).first()
        return help_request






    #THE FOLLOWING METHODS RUN CYPER QUERIES ON THE NEO4j GRAPH DATABASE

    #Create node in neo4j graph database for the user
    def create_node_in_neo4j(self):
        # Establish a connection and create a session
        with neo4j_driver.session() as session:
            # Execute the Cypher query to create a new User node
            session.run("CREATE (:User {id: $id, username: $username, country: $country, city: $city,"
                        "rating_as_deliver: $rating_as_deliver,"
                        "reviews_deliver_counter: $reviews_deliver_counter	})",
                        id=self.id, username=self.username, country=self.country, city=self.city,
                        rating_as_deliver=0, reviews_deliver_counter=0)


    #This function establishes a friend request relationship
    # between the current user and a recipient user in a Neo4j graph database
    def send_friend_request(self, recipient_id):
        with neo4j_driver.session() as session:
            session.run(
                "MATCH (sender:User), (recipient:User) "
                "WHERE sender.id = $sender_id AND recipient.id = $recipient_id "
                "CREATE (sender)-[:FriendRequest]->(recipient)",
                sender_id=self.id, recipient_id=recipient_id
            )




    #This function accepts a friend request from another user
    # identified by their sender_id in a Neo4j graph database.
    # It creates a Friend relationship between the sender and recipient nodes
    def accept_friend_request(self, sender_id):
        with neo4j_driver.session() as session:
            session.run(
                "MATCH (sender:User)-[r:FriendRequest]->(recipient:User) "
                "WHERE sender.id = $sender_id AND recipient.id = $recipient_id "
                "CREATE (sender)-[:Friend]->(recipient), (recipient)-[:Friend]->(sender) "
                "DELETE r",
                sender_id=sender_id, recipient_id=self.id
            )

    # This function rejects a friend request from another user
    # identified by their sender_id in a Neo4j graph database.
    # It deletes the FriendRequest relationship between the sender and recipient nodes
    def reject_friend_request(self, sender_id):
        with neo4j_driver.session() as session:
            session.run(
                "MATCH (sender:User)-[r:FriendRequest]->(recipient:User) "
                "WHERE sender.id = $sender_id AND recipient.id = $recipient_id "
                "DELETE r",
                sender_id=sender_id, recipient_id=self.id
            )




    # This function cancels a friend request sent by the current user
    # to another user identified by their recipient_id in a Neo4j graph database.
    # It runs a Cypher query which deletes the FriendRequest relationship,
    # effectively canceling the friend request.
    def cancel_friend_request(self, recipient_id):
        with neo4j_driver.session() as session:
            session.run(
                "MATCH (sender:User)-[r:FriendRequest]->(recipient:User) "
                "WHERE sender.id = $sender_id AND recipient.id = $recipient_id "
                "DELETE r",
                sender_id=self.id, recipient_id=recipient_id
            )



    # This function checks if the current user has sent a friend request
    # to the specified profile_user in a Neo4j graph database.
    # It returns a Boolean value indicating the result.
    def has_sent_friend_request(self, profile_user):
        query = (
            "MATCH (sender:User)-[r:FriendRequest]->(recipient:User) "
            "WHERE sender.id = $sender_id AND recipient.id = $recipient_id "
            "RETURN COUNT(r) > 0"
        )
        with neo4j_driver.session() as session:
            result = session.run(query, sender_id=self.id, recipient_id=profile_user.id)
            return result.single()[0]





    #This function checks if the current user and
    # the other_user are friends in a Neo4j graph database.
    #  It returns a Boolean value indicating the result.
    def are_friends(self, other_user):
        query = (
            "MATCH (user1:User)-[:Friend]-(user2:User) "
            "WHERE user1.id = $user1_id AND user2.id = $user2_id "
            "RETURN COUNT(*) > 0"
        )

        with neo4j_driver.session() as session:
            result = session.run(query, user1_id=self.id, user2_id=other_user.id)
            return result.single()[0]




    # This fucntion removes a friendship relationship between
    # the current user and a specified friend in a Neo4j graph database.
    def unfriend(self, friend_id):
        with neo4j_driver.session() as session:
            session.run(
                "MATCH (u1:User)-[r:Friend]-(u2:User) "
                "WHERE u1.id = $current_user_id AND u2.id = $friend_id "
                "DELETE r",
                current_user_id=self.id, friend_id=friend_id
            )




    # This function is used to retrieve the recommended friends (People You May Know)
    # for the current user from a Neo4j graph database
    def get_friends_suggestions(self):
        # Retrieve recommended friends attribute
        query = """
            MATCH (u:User {id: $user_id})
            RETURN u.recommended_friends AS recommended_friends
            """
        with neo4j_driver.session() as session:
            result = session.run(query, user_id=self.id).single()

        if result:
            recommended_friends = result["recommended_friends"]
            return recommended_friends
        else:
            return None


    # This function is used to retrieve the friend IDs
    # for the current user from a Neo4j graph database
    def get_friends(self):
        query = """
            MATCH (u:User)-[:Friend]->(f:User)
            WHERE u.id = $user_id
            RETURN  f.id AS friend_id
            """
        with neo4j_driver.session() as session:
            result = session.run(query, user_id=self.id)
            friend_ids = [record["friend_id"] for record in result]
        if friend_ids:
            return friend_ids
        else:
            return None





#The Post class is a database model representing a product request in the application
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(100), nullable=False)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    content = db.Column(db.String(150), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) #author. Why lowercase U ? in the User model,
                                    # we're referencing actual Post *class* and in the foreign key here we're actually referencing
                                    #the *table name* and the column name, so it's a lower case
    country = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=True)
    price_range=db.Column(db.String(20), nullable=False)
    tip_amount = db.Column(db.Float, nullable=False)
    image_file = db.Column(db.String(20), nullable=True)
    help_requests = db.relationship('HelpRequest', foreign_keys='HelpRequest.post_id', backref='post', lazy=True)
    accepted_help_request_id = db.Column(db.Integer, db.ForeignKey('help_request.id'), nullable=True)
    accepted_help_request = db.relationship('HelpRequest', foreign_keys=[accepted_help_request_id])
    is_arrived= db.Column(db.Boolean, nullable=False, default=False) # new field
    is_arrived_confirmed=db.Column(db.Boolean, nullable=False, default=False)
    current_cancelled_request_id=db.Column(db.Integer, db.ForeignKey('help_request.id'), nullable=True)

    shares = db.relationship('PostShare', backref='post', lazy=True) #IGNORE IT, WE DID NOT USE IT

    def __repr__(self):
        return f"User('{self.title}','{self.date_posted}')"





#The HelpRequest class is a database model representing a delivery offer in the application
class HelpRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date_sent = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    tip_amount = db.Column(db.Float, nullable=False)
    accepted = db.Column(db.Boolean, nullable=False, default=False)
    lower_tip_amount = db.Column(db.Float, nullable=True)
    is_waiting_tip_amount = db.Column(db.Boolean, nullable=False, default=False)
    last_delivery_date = db.Column(db.DateTime, nullable=False)
    is_cancelled=db.Column(db.Boolean, nullable=False, default=False)
    is_cancelled_by_deliver=db.Column(db.Boolean, nullable=False, default=False)
    is_completed=db.Column(db.Boolean, nullable=False, default=False)




#The Review class is a database model representing a review in the application
class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reviewed_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    rating = db.Column(db.Float, nullable=False)
    content = db.Column(db.String(250))
    date_added = db.Column(db.DateTime, nullable=False,default=datetime.utcnow)
    is_recipient =db.Column(db.Boolean, nullable=False, default=False)
    is_deliver = db.Column(db.Boolean, nullable=False, default=False)




#The Notification class is a database model representing a notification in the application
class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date_created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    content = db.Column(db.String(200), nullable=False)
    endpoint=db.Column(db.String(30))
    args=db.Column(db.String(200))
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) #user who notified
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) #user who sent the notification by his actions






# _____END OF FILE________EOF____________END OF FILE_______________________



#_____________IGNORE THE REST OF THE FILE__________________________



#WE DID NOT USE IT - INGORE IT
class PostShare(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shared_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

    def __repr__(self):
        return f"PostShare('{self.shared_date}')"





