# FriendShip
## Team members
- Ayala Koslowsky
- Or Daniel
- Matan Kuzi
- Evyatar Gavish


## What is the project about
A social network that connects between users who need products from other countries with their friends who are traveling and willing to deliver them.
Users can create delivery requests on the platform -  specifying the product they need and the country it's located in. Their friends who travel can browse through these requests and offer to deliver the product for a fee.

## Instructions for running the project

1. Download the project files and extract them to a suitable location on your computer.

2. Set up the project environment.

3. In the project environment, install required packages using the following command:  
        pip install flask flask_sqlalchemy flask-bcrypt flask-login Pillow flask_wtf pycountry   
        email_validator requests Flask-Authlib-Client neo4j py2neo phonenumbers
4. Run the app from the project environment using the following command :
     python run.py
(note: the files include an exist local database).

## The structure of the project
1. Friendship package:
   - `init.py`: This file contains the app configuration code, including the setup for 
the local database, Neo4j database, bcrypt for password hashing, login manager, and other configurations.

   - `models.py`: This file includes the class definitions for the local database using SQLAlchemy. It contains classes such as `User`, `Post` (for product requests), `HelpRequest` (for delivery offers), `Review` (for reviews), and `Notification` (for notifications). Each class defines the attributes for the respective entity and may also include additional functions (In the User model we also define functions that perform Cypher queries on the neo4j graph database) 

   - forms.py: This file contains form classes that are used in the app. The form    
     classes inherit from `FlaskForm` and include: `RegistrationForm` (form for user    
     registration), `GoogleRegistrationForm` (form for new users who connect via Google,   
     where they need to input their country, city, and phone number), `LoginForm` (form 
     for user login), `UpdateAccountForm` (form for updating user account information),
     `PostForm` (form for creating new product requests).

   - `routes.py`: This file includes the routing functions for the app. It handles the 
                          request validation and contains the backend code for each route.

   - `templates` directory: This directory contains all the HTML files for the app.

   - `static` directory: This directory contains CSS files and subdirectories for profile pictures, product pictures, and logos.

2. `instance` directory: This directory contains the local database file.

3. `run.py`: This file contains the code to run the app.

4. `script.py`: This file serves as a script to execute various tasks or functions, like run the 'People you may know' recommendation calculation (see an explanation about this function in
 main features/algorithms section).

## Main features/Algorithms:
### Sign in with Google:
Offering the option to sign in with Google makes the registration process easy and quick, as it eliminates the need for users to create a separate account and remember another password. This feature streamlines the onboarding process and enhances user convenience.
We are setting up the Google OAuth 2.0 provider using the OAuth extension.
If the user exists in the local database, they are redirected to the home page.
If the user is new, they are redirected to complete the registration process and when the user's registration details are collected, a new user is created and saved in the local database (and also as a new node on neo4j graph database). The newly registered user is then redirected to the home page. (functions: `google_login()`, `authorize()`, `google_register()` in `routes.py` file)

### Edit personal details:
Users can edit their personal details, including first name, last name, email address, country, city, phone number, and profile picture, using the "edit-account" feature. The updated information is stored in the relational database, while some relevant attributes are synchronized and updated in the user's node within the Neo4j graph database. Additionally, if a new profile picture is uploaded, it is resized and saved. Users can access this functionality through the account page. (function: `account()` in `routes.py` file)

### Create new product requests:
Users can create new product requests, by filling a form (PostForm). If the form is submitted and passes the validations, the product request is created with the appropriate attributes and saved in the local database. (If a picture is included in the form, it is processed and saved in a specific directory). (function: `new_post()` in `routes.py` file)
Similarly, users have the ability to edit their product requests, provided that they have not yet received any delivery offers. They also have the ability to delete their product requests, provided that they have not accepted a delivery offer. (functions: `update_post(post_id)`, `delete_post(post_id)` in `routes.py` file) 

### Send delivery offers: 
When users send a delivery offer, they must provide a delivery fee and a delivery date. If the input passes validation, a new delivery offer is created and stored in the database (`send_help_request(post_id)` in `routes.py`). The sender has the option to cancel the offer, which results in its deletion from the database (`cancel_help_request(post_id)` in `routes.py` file). On the recipient's side, they can either accept the offer (marking it as accepted in the database and preventing new offers), or reject it, resulting in its deletion. (`accept_help_request(help_request_id)` and `reject_help_request(help_request_id)`  in `routes.py`).
Alternatively, the recipient can request a lower delivery fee. If this request passes validation, the offer is marked as awaiting the deliver's response. The deliver is then notified and prompted to select their desired delivery fee, after which the recipient is notified accordingly (`change_tip_amount(request_id)` in `routes.py`).

### Review: 
Users have the option to review each other. When a delivery is made, the deliver rates the recipient, and the review details are stored in the database. Additionally, a notification is sent to the recipient to inform them that the delivery has arrived. The recipient also has the opportunity to rate the deliver, and this rating is saved in the database as well (`send_review(post_id)` in `routes.py`). Users can view these reviews and their content on their profile page (`view_account_reviews(username)` in `routes.py`)
This feature adds a layer of trust and accountability within the community, allowing users to make informed decisions when it comes to selecting friends for shipping items.

### Cancel delivery: 
Both the deliver and the recipient have the ability to cancel a delivery (`cancel_delivery(post_id)` in `routes.py`). The sender can cancel the delivery if it has not been delivered yet. In this case, the recipient need to confirm the cancellation (`confirm_cancelled_delivery(post_id)` in `routes.py`). Similarly, the recipient can cancel the delivery if the delivery date has passed, and they have not received the product.
In cases of cancellation, it is required for both the deliver and the recipient to provide ratings for each other. This ensures that feedback is collected even in cancellation scenarios. However, when the recipient cancels a delivery, it indicates that the deliver has not delivered the product on time. As a result, in this case the deliver is unable to rate the recipient.

### Notifications: 
Keeping users informed and engaged is crucial for providing a seamless experience. The `inject_notifications()` function (in `routes.py` file) retrieves and displays the most recent notifications from the database, limiting them to 6. It also tracks the count of unread notifications for the user. This ensures that users receive timely updates and can easily stay informed about their product delivery progress and other important events. Older notifications can be accessed on the notifications page for a comprehensive history of past events and updates (`notifications(user_id)` in routes.py).
Friends: users can send friend requests to each other, which creates a friend request relationship in the Neo4j graph database. Users can reject a friend request, which deletes the friend request relationship. If a friend request is accepted, a bidirectional friend relationship is created. Users can also unfriend each other, deleting the bidirectional friend relationship in the Neo4j graph database. (functions: `send_friend_request(recipient_id)`, `cancel_friend_request(recipient_id)`, `accept_friend_request(sender_id)`, `reject_friend_request(sender_id)`, `unfriend(friend_id)` in `routes.py`. These functions use functions that defined in `User` class in `models.py` file).

### Smart filtering: 
Allowing users who are traveling to browse and select the products they are willing to ship for their friends is a thoughtful addition. This smart filtering feature helps users find suitable options that align with their travel plans, increasing the likelihood of successful product shipments among friends. The 'home' function (defined in routs.py file) retrieves product requests from the database and applies filters based on selected countries, price ranges, and minimum tip amount. It uses these filters to query the database and fetch the relevant product requests. The filtered product requests are then sorted based on the selected sorting option (default – latest to oldest) before being rendered on the home page. This allows users to view posts that meet their specific criteria and customize their browsing experience. (function: `home()` in `routes.py`)

### Smart Connection to new friends: 
Introducing the "People you may know" and "Relevant Friends for you" features based on Jaccard similarity coefficient and shipping probability respectively is a creative way to enhance user connections. By suggesting potential friends who are more likely to be able to ship their parcels, users can expand their network and find reliable shipping partners. Users can view these suggestions on their profile page. 

##### People you may know - calculation: 
calculated in `recommend_friends_you_may_know(user_id)` function (defined in `script.py` file), which connects to the Neo4j database using the neo4j_driver object , executes a Cypher query to find friend-of-friend (FOF) connections for the user, who are not already direct friends, calculates a Jaccard similarity score between the user and each FOF based on their mutual friend connections, sorts the FOFs based on the scores and updates the user's recommended_friends attribute in the Neo4j database with the recommended friend IDs. To optimize performance, the calculation is not performed each time the user enters their profile page, but rather as a separate step, due to limitations of the free edition of Neo4j, which lacks built-in functionality for more efficient calculations.

##### Relevant Friends for you - calculation:
calculated in `recommend_popular_delivers(user_id)` function (defined in `routes.py` file) which connects to the Neo4j database using the neo4j_driver object, retrieves the user's city and country information from the database, executes a Cypher query to find users from the same country, who have a high rating as a deliver (greater than or equal to 4) and a significant number of delivery reviews (greater than or equal to 20). Then calculates a weighted score for each user based on their rating, review counter, and city similarity to the user, sorts the users based on their scores in descending order, and returns the list of recommended friends IDs.

### Search: 
Users can search other users on the app using their username, first name, last name, or a full name. The search queries, based on the user query input, are performed on the User model in the database, utilizing filter conditions and queries to retrieve the relevant user records matching the search criteria (function: `search()` in `routes.py` file).


